"""Cookie auth middleware and login/logout routes for admin dashboard."""

from __future__ import annotations

import hashlib
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

COOKIE_NAME = "codesight_admin_token"


def _token_for_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _ip_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """Protect all dashboard routes except login and health checks."""

    # // SPEC-014-001: All routes except /login and /api/health require valid auth cookie.
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        if path == "/login" or path == "/api/health":
            return await call_next(request)

        expected_token = str(request.app.state.dashboard_cookie_token)
        actual_token = request.cookies.get(COOKIE_NAME, "")
        if actual_token and secrets.compare_digest(actual_token, expected_token):
            return await call_next(request)

        # // EDGE-014-002: Unauthorized requests redirect to login with original target preserved.
        destination = request.url.path
        if request.url.query:
            destination = f"{destination}?{request.url.query}"
        login_url = f"/login?next={quote(destination, safe='')}"
        return RedirectResponse(url=login_url, status_code=302)


def auth_router() -> APIRouter:
    router = APIRouter()

    @router.get("/login")
    async def login_page(request: Request, next: str = "/", message: str | None = None):
        templates = request.app.state.templates
        if message is None and next and next != "/":
            # // EDGE-014-002: Redirected unauthenticated users get explicit sign-in guidance.
            message = "Please sign in to continue."
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "title": "Admin Login",
                "next": next,
                "message": message,
                "error": None,
            },
        )

    @router.post("/login")
    async def login_submit(
        request: Request,
        api_key: str = Form(default=""),
        next: str = Form(default="/"),
    ):
        expected_key = str(request.app.state.dashboard_api_key)

        # // SPEC-014-001: Login compare uses timing-safe key comparison.
        if not api_key or not secrets.compare_digest(api_key, expected_key):
            ip = request.client.host if request.client else "unknown"
            request.app.state.logger.warning("dashboard.login.failed ip_hash=%s", _ip_hash(ip))
            templates = request.app.state.templates
            response = templates.TemplateResponse(
                request,
                "login.html",
                {
                    "title": "Admin Login",
                    "next": next,
                    "message": None,
                    "error": "Invalid admin API key.",
                },
                status_code=401,
            )
            return response

        response = RedirectResponse(url=next or "/", status_code=302)
        response.set_cookie(
            key=COOKIE_NAME,
            value=_token_for_key(expected_key),
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 12,
        )
        return response

    @router.post("/logout")
    async def logout(request: Request):
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie(COOKIE_NAME)
        return response

    return router


__all__ = ["AdminAuthMiddleware", "COOKIE_NAME", "_token_for_key", "auth_router"]

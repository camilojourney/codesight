"""FastAPI app factory for the CodeSight admin dashboard."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from ..workspace import WorkspaceManager
from .query_log import QueryLogDB

logger = logging.getLogger(__name__)

DASHBOARD_API_KEY_ENV = "CODESIGHT_DASHBOARD_API_KEY"
MISSING_API_KEY_MESSAGE = "CODESIGHT_DASHBOARD_API_KEY is required to run the dashboard."


def create_app(
    *,
    manager: WorkspaceManager | None = None,
    query_log: QueryLogDB | None = None,
    api_key: str | None = None,
):
    """Build a FastAPI app configured with cookie auth and HTML routes."""

    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from fastapi.templating import Jinja2Templates

    from .auth import AdminAuthMiddleware, _token_for_key, auth_router
    from .routes.analytics import analytics_router
    from .routes.sources import sources_router
    from .routes.workspaces import workspaces_router

    dashboard_api_key = (api_key or os.environ.get(DASHBOARD_API_KEY_ENV, "")).strip()
    # // SPEC-014-001: Startup enforces required dashboard API key env var.
    if not dashboard_api_key:
        raise RuntimeError(MISSING_API_KEY_MESSAGE)

    app = FastAPI(title="CodeSight Admin Dashboard", version="0.1.0")
    templates_dir = Path(__file__).parent / "templates"

    app.state.logger = logger
    app.state.dashboard_api_key = dashboard_api_key
    app.state.dashboard_cookie_token = _token_for_key(dashboard_api_key)
    app.state.manager = manager or WorkspaceManager()
    app.state.query_log = query_log or QueryLogDB()
    app.state.templates = Jinja2Templates(directory=str(templates_dir))
    app.state.sync_inflight: set[str] = set()

    app.add_middleware(AdminAuthMiddleware)

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        # // SPEC-014-001: Structured request logging records route status and latency.
        started = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        route = request.scope.get("path")
        logger.info(
            "dashboard.request method=%s route=%s status=%d latency_ms=%.2f",
            request.method,
            route,
            response.status_code,
            latency_ms,
        )
        return response

    @app.get("/api/health")
    async def health() -> JSONResponse:
        # // SPEC-014-001: Health endpoint is always available without auth.
        return JSONResponse({"status": "ok"})

    app.include_router(auth_router())
    app.include_router(workspaces_router())
    app.include_router(sources_router())
    app.include_router(analytics_router())

    return app


def run_dashboard(*, host: str = "0.0.0.0", port: int = 8080) -> Any:
    """Launch the dashboard server with uvicorn."""

    import uvicorn

    app = create_app()
    return uvicorn.run(app, host=host, port=port)


__all__ = ["DASHBOARD_API_KEY_ENV", "MISSING_API_KEY_MESSAGE", "create_app", "run_dashboard"]

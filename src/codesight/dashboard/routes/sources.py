"""Workspace source management and M365 browse routes."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Form, Request

from ...connectors import M365Authenticator
from ...types import DataSource
from . import (
    fetch_workspace_sources,
    get_manager,
    get_templates,
    source_config_value,
    workspace_not_found_response,
)

logger = logging.getLogger(__name__)

SOURCE_KEY_MAP = {
    "drive": "path",
    "mail": "mailbox",
    "notes": "notebook",
    "sharepoint": "site_url",
    "local": "path",
}

NOT_CONNECTED_MESSAGE = "Not connected to M365. Run 'codesight sync --source m365' to authenticate."
TOKEN_EXPIRED_MESSAGE = "M365 token expired. Run 'codesight sync --source m365' to re-authenticate."
TIMEOUT_MESSAGE = "M365 browser timed out after 10 seconds. Enter source manually."


def _render_sources_fragment(request: Request, workspace_id: str, error: str | None = None):
    manager = get_manager(request)
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "workspaces/_sources.html",
        {
            "workspace_id": workspace_id,
            "sources": fetch_workspace_sources(manager, workspace_id),
            "source_error": error,
            "source_config_value": source_config_value,
        },
    )


def _silent_graph_token() -> str:
    # // SPEC-014-004: Browser checks existing M365 token cache without interactive auth flow.
    auth = M365Authenticator()
    accounts = auth._app.get_accounts()  # noqa: SLF001 - needed for silent token lookup.
    if not accounts:
        raise PermissionError(NOT_CONNECTED_MESSAGE)

    token_result = auth._app.acquire_token_silent(  # noqa: SLF001
        auth.scopes,
        account=accounts[0],
        force_refresh=False,
    )
    if not token_result or "access_token" not in token_result:
        raise RuntimeError(TOKEN_EXPIRED_MESSAGE)
    return str(token_result["access_token"])


def _m365_endpoint(source_type: str) -> tuple[str, dict[str, str]]:
    if source_type == "drive":
        return (
            "https://graph.microsoft.com/v1.0/me/drive/root/children",
            {"$top": "50", "$select": "id,name,webUrl,parentReference,folder,file"},
        )
    if source_type == "mail":
        return (
            "https://graph.microsoft.com/v1.0/me/mailFolders",
            {"$top": "50", "$select": "id,displayName,totalItemCount"},
        )
    if source_type == "notes":
        return (
            "https://graph.microsoft.com/v1.0/me/onenote/notebooks",
            {"$top": "50", "$select": "id,displayName,links"},
        )
    if source_type == "sharepoint":
        return (
            "https://graph.microsoft.com/v1.0/sites",
            {"search": "*", "$top": "50", "$select": "id,displayName,webUrl"},
        )
    raise ValueError(f"Unsupported source type '{source_type}'.")


def _normalize_drive_path(raw_parent: str, name: str) -> str:
    normalized_parent = raw_parent.replace("/drive/root:", "")
    normalized_parent = normalized_parent.rstrip("/")
    if not normalized_parent:
        return f"/{name}"
    return f"{normalized_parent}/{name}"


def _browser_rows(source_type: str, payload: dict) -> list[dict[str, str]]:
    values = payload.get("value", [])
    rows: list[dict[str, str]] = []
    for item in values:
        item_id = str(item.get("id", ""))
        label = ""
        value = ""

        if source_type == "drive":
            name = str(item.get("name", ""))
            parent_path = str(item.get("parentReference", {}).get("path", ""))
            label = name
            value = _normalize_drive_path(parent_path, name)
        elif source_type == "mail":
            label = str(item.get("displayName", ""))
            value = label
        elif source_type == "notes":
            label = str(item.get("displayName", ""))
            value = label
        elif source_type == "sharepoint":
            label = str(item.get("displayName", ""))
            value = str(item.get("webUrl", ""))

        if not label and not value:
            continue

        rows.append(
            {
                "id": item_id,
                "label": label or value,
                "value": value,
                "url": str(item.get("webUrl", "")),
            }
        )

    return rows


def sources_router() -> APIRouter:
    router = APIRouter()

    @router.post("/workspaces/{workspace_id}/sources")
    async def workspace_add_source(
        request: Request,
        workspace_id: str,
        source_type: str = Form(default=""),
        source_value: str = Form(default=""),
    ):
        manager = get_manager(request)
        try:
            manager.get(workspace_id)
        except ValueError:
            return workspace_not_found_response(request)

        source_type = source_type.strip().lower()
        source_value = source_value.strip()
        source_key = SOURCE_KEY_MAP.get(source_type)
        if not source_type or not source_key or not source_value:
            return _render_sources_fragment(
                request,
                workspace_id,
                error="Source type and value are required.",
            )

        source = DataSource(source_type=source_type, source_config={source_key: source_value})
        try:
            # // SPEC-014-004: Source writes always delegate to WorkspaceManager validation.
            manager.add_source(workspace_id, source)
        except ValueError as exc:
            return _render_sources_fragment(request, workspace_id, error=str(exc))

        return _render_sources_fragment(request, workspace_id)

    @router.post("/workspaces/{workspace_id}/sources/{source_id}/delete")
    async def workspace_remove_source(request: Request, workspace_id: str, source_id: str):
        manager = get_manager(request)
        try:
            manager.get(workspace_id)
        except ValueError:
            return workspace_not_found_response(request)

        try:
            manager.remove_source(workspace_id, source_id)
        except ValueError as exc:
            return _render_sources_fragment(request, workspace_id, error=str(exc))

        return _render_sources_fragment(request, workspace_id)

    @router.get("/workspaces/{workspace_id}/sources/browse")
    async def workspace_browse_m365(request: Request, workspace_id: str, type: str):
        manager = get_manager(request)
        templates = get_templates(request)

        try:
            manager.get(workspace_id)
        except ValueError:
            return workspace_not_found_response(request)

        source_type = type.strip().lower()
        error: str | None = None
        rows: list[dict[str, str]] = []

        try:
            token = _silent_graph_token()
            endpoint, params = _m365_endpoint(source_type)
            headers = {"Authorization": f"Bearer {token}"}
            if source_type == "sharepoint":
                headers["ConsistencyLevel"] = "eventual"

            with httpx.Client(timeout=10.0) as client:
                response = client.get(endpoint, params=params, headers=headers)

            if response.status_code == 401:
                raise RuntimeError(TOKEN_EXPIRED_MESSAGE)
            if response.status_code >= 400:
                raise RuntimeError(response.text[:200] or "Microsoft Graph request failed.")

            rows = _browser_rows(source_type, response.json())
        except PermissionError:
            error = NOT_CONNECTED_MESSAGE
        except ValueError as exc:
            if "Missing CODESIGHT_M365_CLIENT_ID" in str(exc):
                error = NOT_CONNECTED_MESSAGE
            else:
                error = str(exc)
        except RuntimeError as exc:
            text = str(exc)
            if text == TOKEN_EXPIRED_MESSAGE:
                error = TOKEN_EXPIRED_MESSAGE
            else:
                error = text
        except httpx.TimeoutException:
            # // EDGE-014-005: M365 browse timeout fails with deterministic message and no crash.
            request.app.state.logger.warning(
                "dashboard.sources.browse.timeout workspace_id=%s source_type=%s",
                workspace_id,
                source_type,
            )
            error = TIMEOUT_MESSAGE

        return templates.TemplateResponse(
            request,
            "workspaces/_browse_results.html",
            {
                "source_type": source_type,
                "required_key": SOURCE_KEY_MAP.get(source_type, "value"),
                "rows": rows,
                "error": error,
            },
        )

    return router


__all__ = ["sources_router"]

"""Workspace CRUD, sync, and ACL routes."""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...types import DataSource
from . import (
    acl_contains_email,
    duration_seconds,
    fetch_sync_history,
    fetch_workspace_acl,
    fetch_workspace_sources,
    format_timestamp,
    get_manager,
    get_templates,
    is_htmx,
    latest_sync_run,
    shorten_error,
    source_config_value,
    workspace_not_found_response,
    workspace_rows,
)

logger = logging.getLogger(__name__)

VALID_SOURCE_TYPES = ("drive", "mail", "notes", "sharepoint", "local")
SOURCE_KEY_MAP = {
    "drive": "path",
    "mail": "mailbox",
    "notes": "notebook",
    "sharepoint": "site_url",
    "local": "path",
}


def _build_source(source_type: str, source_value: str) -> DataSource | None:
    source_type = source_type.strip().lower()
    source_value = source_value.strip()
    if not source_type or not source_value:
        return None
    key = SOURCE_KEY_MAP.get(source_type)
    if key is None:
        return DataSource(source_type=source_type, source_config={"value": source_value})
    return DataSource(source_type=source_type, source_config={key: source_value})


def _sync_task(app, workspace_id: str) -> None:
    manager = app.state.manager
    inflight = app.state.sync_inflight
    try:
        manager.sync(workspace_id)
    except RuntimeError as exc:
        app.state.logger.warning(
            "dashboard.sync.conflict workspace_id=%s error=%s",
            workspace_id,
            exc,
        )
    except Exception as exc:  # pragma: no cover - defensive error logging for background task.
        app.state.logger.exception(
            "dashboard.sync.failed workspace_id=%s error=%s",
            workspace_id,
            exc,
        )
    finally:
        inflight.discard(workspace_id)


def _render_acl_fragment(
    request: Request,
    workspace_id: str,
    error: str | None = None,
) -> HTMLResponse:
    manager = get_manager(request)
    templates = get_templates(request)
    acl_entries = fetch_workspace_acl(manager, workspace_id)
    return templates.TemplateResponse(
        request,
        "workspaces/_acl.html",
        {
            "workspace_id": workspace_id,
            "acl_entries": acl_entries,
            "acl_error": error,
        },
    )


def _render_sync_status_fragment(
    request: Request,
    workspace,
    status_code: int = 200,
) -> HTMLResponse:
    templates = get_templates(request)
    manager = get_manager(request)
    latest_run = latest_sync_run(manager, workspace.id)
    return templates.TemplateResponse(
        request,
        "workspaces/_sync_status.html",
        {
            "workspace": workspace,
            "latest_run": latest_run,
            "duration_seconds": duration_seconds,
            "format_timestamp": format_timestamp,
        },
        status_code=status_code,
    )


def _render_workspace_detail(
    request: Request,
    workspace,
    *,
    message: str | None = None,
    error: str | None = None,
    form_error: str | None = None,
) -> HTMLResponse:
    manager = get_manager(request)
    templates = get_templates(request)
    sync_history = fetch_sync_history(manager, workspace.id, limit=20)
    return templates.TemplateResponse(
        request,
        "workspaces/detail.html",
        {
            "title": f"Workspace: {workspace.name}",
            "workspace": workspace,
            "latest_run": sync_history[0] if sync_history else None,
            "sources": fetch_workspace_sources(manager, workspace.id),
            "source_config_value": source_config_value,
            "sync_history": sync_history,
            "acl_entries": fetch_workspace_acl(manager, workspace.id),
            "message": message,
            "error": error,
            "form_error": form_error,
            "duration_seconds": duration_seconds,
            "format_timestamp": format_timestamp,
            "shorten_error": shorten_error,
            "valid_source_types": VALID_SOURCE_TYPES,
        },
    )


def workspaces_router() -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def workspace_list(
        request: Request,
        message: str | None = None,
        error: str | None = None,
    ):
        manager = get_manager(request)
        templates = get_templates(request)
        rows = workspace_rows(manager)
        return templates.TemplateResponse(
            request,
            "workspaces/list.html",
            {
                "title": "Workspaces",
                "workspace_rows": rows,
                "format_timestamp": format_timestamp,
                "message": message,
                "error": error,
            },
        )

    @router.get("/workspaces/new")
    async def workspace_new(request: Request):
        templates = get_templates(request)
        return templates.TemplateResponse(
            request,
            "workspaces/form.html",
            {
                "title": "Create Workspace",
                "valid_source_types": VALID_SOURCE_TYPES,
                "form_error": None,
                "form_values": {},
            },
        )

    @router.post("/workspaces")
    async def workspace_create(
        request: Request,
        name: str = Form(default=""),
        description: str = Form(default=""),
        source_type: str = Form(default=""),
        source_value: str = Form(default=""),
        allowed_email: str = Form(default=""),
    ):
        manager = get_manager(request)
        templates = get_templates(request)

        sources: list[DataSource] = []
        parsed_source = _build_source(source_type, source_value)
        if parsed_source is not None:
            sources.append(parsed_source)

        allowed_emails = [allowed_email.strip()] if allowed_email.strip() else []

        try:
            # // SPEC-014-003: Create delegates validation/persistence to WorkspaceManager.
            workspace = manager.create(
                name=name.strip(),
                description=(description.strip() or None),
                sources=sources,
                allowed_emails=allowed_emails,
            )
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "workspaces/form.html",
                {
                    "title": "Create Workspace",
                    "valid_source_types": VALID_SOURCE_TYPES,
                    "form_error": str(exc),
                    "form_values": {
                        "name": name,
                        "description": description,
                        "source_type": source_type,
                        "source_value": source_value,
                        "allowed_email": allowed_email,
                    },
                },
                status_code=400,
            )

        # // SPEC-014-003: Successful create redirects to workspace detail.
        return RedirectResponse(url=f"/workspaces/{workspace.id}", status_code=302)

    @router.get("/workspaces/{workspace_id}")
    async def workspace_detail(
        request: Request,
        workspace_id: str,
        message: str | None = None,
        error: str | None = None,
    ):
        manager = get_manager(request)
        try:
            workspace = manager.get(workspace_id)
        except ValueError:
            return workspace_not_found_response(request)
        return _render_workspace_detail(request, workspace, message=message, error=error)

    @router.post("/workspaces/{workspace_id}")
    async def workspace_update(
        request: Request,
        workspace_id: str,
        name: str = Form(default=""),
        description: str = Form(default=""),
    ):
        manager = get_manager(request)
        try:
            workspace = manager.get(workspace_id)
        except ValueError:
            return workspace_not_found_response(request)

        try:
            # // SPEC-014-003: Workspace metadata updates reuse existing workspace ID.
            updated = manager.update(
                workspace.id,
                name=name.strip() or workspace.name,
                description=description.strip() or None,
            )
        except ValueError as exc:
            return _render_workspace_detail(request, workspace, form_error=str(exc))

        return RedirectResponse(
            url=f"/workspaces/{updated.id}?message={quote_plus('Workspace updated.')}",
            status_code=302,
        )

    @router.post("/workspaces/{workspace_id}/delete")
    async def workspace_delete(request: Request, workspace_id: str):
        manager = get_manager(request)
        try:
            workspace = manager.get(workspace_id)
        except ValueError:
            return workspace_not_found_response(request)

        try:
            manager.delete(workspace.id)
        except ValueError as exc:
            if is_htmx(request):
                return HTMLResponse(str(exc), status_code=400)
            return RedirectResponse(
                url=f"/workspaces/{workspace.id}?error={quote_plus(str(exc))}",
                status_code=302,
            )

        message = quote_plus(f"Deleted workspace '{workspace.name}'.")
        return RedirectResponse(url=f"/?message={message}", status_code=302)

    @router.post("/workspaces/{workspace_id}/sync")
    async def workspace_sync_trigger(
        request: Request,
        workspace_id: str,
        background_tasks: BackgroundTasks,
    ):
        manager = get_manager(request)
        try:
            workspace = manager.get(workspace_id)
        except ValueError:
            return workspace_not_found_response(request)

        if workspace.sync_status == "syncing" or workspace.id in request.app.state.sync_inflight:
            # // EDGE-014-004: Concurrent sync trigger returns deterministic 409 conflict error.
            message = f"Sync already in progress for workspace '{workspace.name}'."
            request.app.state.logger.warning(
                "dashboard.sync.conflict workspace_id=%s",
                workspace.id,
            )
            return HTMLResponse(message, status_code=409)

        request.app.state.sync_inflight.add(workspace.id)
        background_tasks.add_task(_sync_task, request.app, workspace.id)
        request.app.state.logger.info("dashboard.sync.triggered workspace_id=%s", workspace.id)

        # // SPEC-014-005: Sync trigger returns 202 while background task executes.
        refreshing_workspace = workspace.model_copy(update={"sync_status": "syncing"})
        return _render_sync_status_fragment(request, refreshing_workspace, status_code=202)

    @router.get("/workspaces/{workspace_id}/sync-status")
    async def workspace_sync_status(request: Request, workspace_id: str):
        manager = get_manager(request)
        try:
            workspace = manager.get(workspace_id)
        except ValueError:
            return workspace_not_found_response(request)

        return _render_sync_status_fragment(request, workspace)

    @router.post("/workspaces/{workspace_id}/access")
    async def workspace_access_add(
        request: Request,
        workspace_id: str,
        email: str = Form(default=""),
    ):
        manager = get_manager(request)
        try:
            manager.get(workspace_id)
        except ValueError:
            return workspace_not_found_response(request)

        normalized = email.strip().lower()
        if not normalized:
            return _render_acl_fragment(request, workspace_id, error="Email is required.")

        # // SPEC-014-007: Duplicate ACL add returns inline validation error.
        if acl_contains_email(manager, workspace_id, normalized):
            return _render_acl_fragment(
                request,
                workspace_id,
                error=f"{normalized} is already in the access list.",
            )

        try:
            manager.allow(workspace_id, normalized)
        except ValueError as exc:
            return _render_acl_fragment(request, workspace_id, error=str(exc))

        return _render_acl_fragment(request, workspace_id)

    @router.post("/workspaces/{workspace_id}/access/{email}/delete")
    async def workspace_access_delete(request: Request, workspace_id: str, email: str):
        manager = get_manager(request)
        try:
            manager.get(workspace_id)
        except ValueError:
            return workspace_not_found_response(request)

        manager.deny(workspace_id, email)
        return _render_acl_fragment(request, workspace_id)

    return router


__all__ = ["workspaces_router"]

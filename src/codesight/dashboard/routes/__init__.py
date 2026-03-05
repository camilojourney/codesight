"""Shared route helpers for dashboard routers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...types import DataSource, SyncRunResult
from ...workspace import WorkspaceManager


def get_manager(request: Request) -> WorkspaceManager:
    return request.app.state.manager


def get_templates(request: Request):
    return request.app.state.templates


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def format_timestamp(value: str | None) -> str:
    parsed = parse_iso(value)
    if parsed is None:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def duration_seconds(started_at: str, completed_at: str | None) -> str:
    started = parse_iso(started_at)
    completed = parse_iso(completed_at)
    if started is None or completed is None:
        return ""
    seconds = max(0.0, (completed - started).total_seconds())
    return f"{seconds:.1f}s"


def shorten_error(message: str | None, max_chars: int = 200) -> str:
    if not message:
        return ""
    text = message.strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3]}..."


def workspace_not_found_response(request: Request):
    if is_htmx(request):
        # // EDGE-014-007: HTMX actions return 404 and redirect when workspace is deleted.
        response = HTMLResponse("Workspace not found.", status_code=404)
        response.headers["HX-Redirect"] = "/?error=Workspace+not+found."
        return response
    return RedirectResponse(url="/?error=Workspace+not+found.", status_code=302)


def fetch_workspace_sources(manager: WorkspaceManager, workspace_id: str) -> list[DataSource]:
    # // SPEC-014-004: Source list reads canonical rows from Spec-013 schema.
    return manager._list_sources(workspace_id)


def fetch_workspace_acl(manager: WorkspaceManager, workspace_id: str) -> list[str]:
    with manager.db.connection() as conn:
        rows = conn.execute(
            """
            SELECT email FROM workspace_access
            WHERE workspace_id = ?
            ORDER BY email ASC
            """,
            (workspace_id,),
        ).fetchall()
    return [str(row["email"]) for row in rows]


def acl_contains_email(manager: WorkspaceManager, workspace_id: str, email: str) -> bool:
    normalized = email.strip().lower()
    with manager.db.connection() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM workspace_access
            WHERE workspace_id = ? AND email = ?
            LIMIT 1
            """,
            (workspace_id, normalized),
        ).fetchone()
    return row is not None


def fetch_sync_history(
    manager: WorkspaceManager,
    workspace_id: str,
    limit: int = 20,
) -> list[SyncRunResult]:
    # // SPEC-014-006: Sync history uses last N rows from sync_runs newest-first.
    with manager.db.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, workspace_id, started_at, completed_at, status,
                   files_added, files_updated, files_deleted, error_message
            FROM sync_runs
            WHERE workspace_id = ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (workspace_id, limit),
        ).fetchall()
    return [
        SyncRunResult(
            id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            started_at=str(row["started_at"]),
            completed_at=row["completed_at"],
            status=str(row["status"]),
            files_added=int(row["files_added"]),
            files_updated=int(row["files_updated"]),
            files_deleted=int(row["files_deleted"]),
            error_message=row["error_message"],
        )
        for row in rows
    ]


def latest_sync_run(manager: WorkspaceManager, workspace_id: str) -> SyncRunResult | None:
    history = fetch_sync_history(manager, workspace_id, limit=1)
    return history[0] if history else None


def workspace_rows(manager: WorkspaceManager) -> list[dict[str, Any]]:
    # // SPEC-014-002: List rows include source_count, last_sync, item_count, and sync_status.
    rows: list[dict[str, Any]] = []
    for workspace in manager.list():
        with manager.db.connection() as conn:
            source_count = conn.execute(
                "SELECT COUNT(*) AS count FROM data_sources WHERE workspace_id = ?",
                (workspace.id,),
            ).fetchone()["count"]
            latest_run = conn.execute(
                """
                SELECT files_added, files_updated, files_deleted
                FROM sync_runs
                WHERE workspace_id = ?
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (workspace.id,),
            ).fetchone()
        item_count = 0
        if latest_run is not None:
            item_count = max(
                0,
                int(latest_run["files_added"]) + int(latest_run["files_updated"])
                - int(latest_run["files_deleted"]),
            )
        rows.append(
            {
                "workspace": workspace,
                "source_count": int(source_count),
                "item_count": item_count,
                "last_sync": workspace.last_synced_at,
            }
        )
    return rows


def file_counter_for_workspace_data(manager: WorkspaceManager, workspace_id: str) -> int:
    root = manager.workspace_data_dir(workspace_id)
    if not root.exists():
        return 0
    return sum(1 for file_path in Path(root).rglob("*") if file_path.is_file())


def source_config_value(source: DataSource) -> str:
    key_map = {
        "drive": "path",
        "mail": "mailbox",
        "notes": "notebook",
        "sharepoint": "site_url",
        "local": "path",
    }
    key = key_map.get(source.source_type)
    if not key:
        return json.dumps(source.source_config, sort_keys=True)
    value = source.source_config.get(key, "")
    return str(value)

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import quote

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from codesight import __main__ as cli
from codesight.dashboard.app import DASHBOARD_API_KEY_ENV, MISSING_API_KEY_MESSAGE, create_app
from codesight.dashboard.auth import COOKIE_NAME
from codesight.dashboard.query_log import QueryLogDB
from codesight.workspace import WorkspaceManager

API_KEY = "dashboard-test-key"


def _manager(tmp_path):
    root = tmp_path / ".codesight"
    return WorkspaceManager(db_path=root / "workspaces.db", data_root=root / "data")


def _query_log(tmp_path):
    return QueryLogDB(db_path=tmp_path / ".codesight" / "query_log.db")


def _login(client: TestClient):
    response = client.post(
        "/login",
        data={"api_key": API_KEY, "next": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"


@pytest.fixture
def dashboard_context(tmp_path):
    manager = _manager(tmp_path)
    query_log = _query_log(tmp_path)
    app = create_app(manager=manager, query_log=query_log, api_key=API_KEY)
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, manager=manager, query_log=query_log, app=app)


# SPEC-014-001

def test_spec_014_001_startup_without_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path):
    manager = _manager(tmp_path)
    query_log = _query_log(tmp_path)
    monkeypatch.delenv(DASHBOARD_API_KEY_ENV, raising=False)

    with pytest.raises(RuntimeError) as exc:
        create_app(manager=manager, query_log=query_log)

    assert str(exc.value) == MISSING_API_KEY_MESSAGE


def test_spec_014_001_health_no_auth(dashboard_context):
    response = dashboard_context.client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_spec_014_001_protected_route_redirects(dashboard_context):
    response = dashboard_context.client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=%2F"


def test_spec_014_001_login_correct_key(dashboard_context):
    response = dashboard_context.client.post(
        "/login",
        data={"api_key": API_KEY, "next": "/"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/"
    assert COOKIE_NAME in response.cookies
    assert COOKIE_NAME in response.headers.get("set-cookie", "")


def test_spec_014_001_login_wrong_key(dashboard_context):
    response = dashboard_context.client.post(
        "/login",
        data={"api_key": "wrong-key", "next": "/"},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "Invalid admin API key." in response.text


# SPEC-014-002

def test_spec_014_002_workspace_list_renders_rows(dashboard_context):
    manager = dashboard_context.manager
    workspace_never = manager.create("Alpha")
    workspace_syncing = manager.create("Bravo")
    workspace_ok = manager.create("Charlie")
    workspace_error = manager.create("Delta")

    now = datetime.now(timezone.utc).isoformat()
    with manager.db.transaction() as conn:
        conn.execute(
            "UPDATE workspaces SET sync_status = ?, last_synced_at = ? WHERE id = ?",
            ("syncing", now, workspace_syncing.id),
        )
        conn.execute(
            "UPDATE workspaces SET sync_status = ?, last_synced_at = ? WHERE id = ?",
            ("ok", now, workspace_ok.id),
        )
        conn.execute(
            "UPDATE workspaces SET sync_status = ?, last_synced_at = ? WHERE id = ?",
            ("error", now, workspace_error.id),
        )

    _login(dashboard_context.client)
    response = dashboard_context.client.get("/")

    assert response.status_code == 200
    assert response.text.count('<td><a href="/workspaces/') == 4
    assert "Name" in response.text
    assert "Source Count" in response.text
    assert "Last Sync" in response.text
    assert "Item Count" in response.text
    assert "Sync Status" in response.text
    assert workspace_never.name in response.text
    assert workspace_syncing.name in response.text
    assert workspace_ok.name in response.text
    assert workspace_error.name in response.text
    for status in ("never", "syncing", "ok", "error"):
        assert f'class="badge {status}">{status}</span>' in response.text


def test_spec_014_002_workspace_list_empty_state(dashboard_context):
    _login(dashboard_context.client)
    response = dashboard_context.client.get("/")

    assert response.status_code == 200
    assert "No workspaces yet." in response.text
    assert '<a href="/workspaces/new">Create one now.</a>' in response.text


def test_spec_014_002_last_sync_never_when_null(dashboard_context):
    dashboard_context.manager.create("Alpha")

    _login(dashboard_context.client)
    response = dashboard_context.client.get("/")

    assert response.status_code == 200
    assert "Never" in response.text


# SPEC-014-003

def test_spec_014_003_create_workspace_success(dashboard_context):
    _login(dashboard_context.client)

    form_response = dashboard_context.client.get("/workspaces/new")
    assert form_response.status_code == 200
    assert "Name" in form_response.text
    assert "Description" in form_response.text
    assert "Initial Source (Optional)" in form_response.text
    assert "Initial Access (Optional)" in form_response.text

    source_dir = dashboard_context.manager.data_root / "seed-source"
    source_dir.mkdir(parents=True, exist_ok=True)
    create_response = dashboard_context.client.post(
        "/workspaces",
        data={
            "name": "Sales Workspace",
            "description": "Sales docs",
            "source_type": "local",
            "source_value": str(source_dir),
            "allowed_email": "owner@example.com",
        },
        follow_redirects=False,
    )

    assert create_response.status_code == 302
    assert create_response.headers["location"].startswith("/workspaces/")
    created = dashboard_context.manager.get("Sales Workspace")
    assert create_response.headers["location"] == f"/workspaces/{created.id}"


def test_spec_014_003_duplicate_name_error(dashboard_context):
    dashboard_context.manager.create("Sales")

    _login(dashboard_context.client)
    response = dashboard_context.client.post(
        "/workspaces",
        data={"name": "sales", "description": "duplicate"},
    )

    assert response.status_code == 400
    assert "Workspace &#39;Sales&#39; already exists." in response.text


def test_spec_014_003_invalid_name_error(dashboard_context):
    _login(dashboard_context.client)
    response = dashboard_context.client.post(
        "/workspaces",
        data={"name": "bad/name", "description": "invalid"},
    )

    assert response.status_code == 400
    assert (
        "Workspace name is invalid. Use 1-100 characters: letters, numbers, space, _, -, ."
        in response.text
    )


# SPEC-014-005

def test_spec_014_005_sync_trigger_202(dashboard_context, monkeypatch: pytest.MonkeyPatch):
    import codesight.dashboard.routes.workspaces as workspaces_routes

    monkeypatch.setattr(workspaces_routes, "_sync_task", lambda app, workspace_id: None)

    workspace = dashboard_context.manager.create("Ops")
    _login(dashboard_context.client)

    response = dashboard_context.client.post(
        f"/workspaces/{workspace.id}/sync",
        follow_redirects=False,
    )

    assert response.status_code == 202
    assert 'class="badge syncing">syncing</span>' in response.text
    assert 'hx-trigger="every 30s"' in response.text

    started_at = datetime.now(timezone.utc).isoformat()
    completed_at = datetime.now(timezone.utc).isoformat()
    with dashboard_context.manager.db.transaction() as conn:
        conn.execute(
            "UPDATE workspaces SET sync_status = ?, last_synced_at = ? WHERE id = ?",
            ("ok", completed_at, workspace.id),
        )
        conn.execute(
            """
            INSERT INTO sync_runs(
                id, workspace_id, started_at, completed_at, status,
                files_added, files_updated, files_deleted, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                workspace.id,
                started_at,
                completed_at,
                "ok",
                3,
                2,
                1,
                None,
            ),
        )

    status_response = dashboard_context.client.get(f"/workspaces/{workspace.id}/sync-status")
    assert status_response.status_code == 200
    assert 'hx-trigger="every 30s"' not in status_response.text
    assert "Added: 3 | Updated: 2 | Deleted: 1" in status_response.text


def test_spec_014_005_concurrent_sync_409(dashboard_context):
    workspace = dashboard_context.manager.create("Ops")
    with dashboard_context.manager.db.transaction() as conn:
        conn.execute(
            "UPDATE workspaces SET sync_status = ? WHERE id = ?",
            ("syncing", workspace.id),
        )

    _login(dashboard_context.client)
    response = dashboard_context.client.post(f"/workspaces/{workspace.id}/sync")

    assert response.status_code == 409
    assert f"Sync already in progress for workspace '{workspace.name}'." in response.text


# SPEC-014-007

def test_spec_014_007_acl_add_email(dashboard_context):
    workspace = dashboard_context.manager.create("ACL")

    _login(dashboard_context.client)
    response = dashboard_context.client.post(
        f"/workspaces/{workspace.id}/access",
        data={"email": "User@Example.com"},
    )

    assert response.status_code == 200
    assert "user@example.com" in response.text
    assert dashboard_context.manager.check_access(workspace.id, "user@example.com") is True


def test_spec_014_007_acl_remove_email(dashboard_context):
    workspace = dashboard_context.manager.create("ACL")
    dashboard_context.manager.allow(workspace.id, "user@example.com")

    _login(dashboard_context.client)
    response = dashboard_context.client.post(
        f"/workspaces/{workspace.id}/access/{quote('user@example.com', safe='')}/delete"
    )

    assert response.status_code == 200
    assert "No users have access. This workspace is private." in response.text
    assert dashboard_context.manager.check_access(workspace.id, "user@example.com") is False


def test_spec_014_007_acl_duplicate_error(dashboard_context):
    workspace = dashboard_context.manager.create("ACL")
    dashboard_context.manager.allow(workspace.id, "user@example.com")

    _login(dashboard_context.client)
    response = dashboard_context.client.post(
        f"/workspaces/{workspace.id}/access",
        data={"email": "USER@example.com"},
    )

    assert response.status_code == 200
    assert "user@example.com is already in the access list." in response.text


# SPEC-014-008

def test_spec_014_008_analytics_empty_state(dashboard_context):
    _login(dashboard_context.client)
    response = dashboard_context.client.get("/analytics")

    assert response.status_code == 200
    assert "No queries recorded yet." in response.text
    assert "P50 Latency" in response.text
    assert "P95 Latency" in response.text
    assert "- ms" in response.text


# EDGE

def test_edge_014_001_missing_api_key(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
):
    monkeypatch.delenv(DASHBOARD_API_KEY_ENV, raising=False)
    args = SimpleNamespace(host="127.0.0.1", port=8080)

    with pytest.raises(SystemExit) as exc:
        cli._run_dashboard(args)

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert captured.out.strip() == MISSING_API_KEY_MESSAGE


def test_edge_014_002_unauthenticated_redirect(dashboard_context):
    response = dashboard_context.client.get("/workspaces/new?tab=sources", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=%2Fworkspaces%2Fnew%3Ftab%3Dsources"

    login_response = dashboard_context.client.get(response.headers["location"])
    assert login_response.status_code == 200
    assert "Please sign in to continue." in login_response.text


def test_edge_014_003_invalid_login_key(dashboard_context):
    response = dashboard_context.client.post(
        "/login",
        data={"api_key": "wrong-key", "next": "/"},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "Invalid admin API key." in response.text
    assert COOKIE_NAME not in response.headers.get("set-cookie", "")


def test_edge_014_008_missing_query_log_db(tmp_path):
    manager = _manager(tmp_path)
    query_log_path = tmp_path / "missing" / "query_log.db"
    assert not query_log_path.exists()

    app = create_app(
        manager=manager,
        query_log=QueryLogDB(db_path=query_log_path),
        api_key=API_KEY,
    )
    with TestClient(app) as client:
        _login(client)
        response = client.get("/analytics")

    assert response.status_code == 200
    assert "No queries recorded yet." in response.text
    assert query_log_path.exists()

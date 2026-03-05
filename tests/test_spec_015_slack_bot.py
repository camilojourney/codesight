from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import codesight.bot.slack as slack_module
from codesight.bot.blocks import answer_blocks, source_line, truncate_answer
from codesight.bot.slack import (
    LLM_FALLBACK,
    MISSING_BOT_TOKEN,
    MISSING_EMAIL_SCOPE,
    MISSING_SIGNING_SECRET,
    MISSING_WORKSPACE,
    RATE_LIMIT_EXHAUSTED,
    TRUNCATION_NOTE,
    USAGE_SLASH,
    _load_startup_config,
    _normalize_question,
    _strip_mention_prefix,
)
from codesight.types import Answer, RepoStatus, SearchResult
from codesight.workspace import WorkspaceManager


class _StubEngine:
    def __init__(self) -> None:
        self.ask_calls: list[str] = []
        self.search_calls: list[str] = []
        self.status_value = RepoStatus(
            repo_path="/tmp/data",
            indexed=True,
            chunk_count=2,
            files_indexed=1,
            stale=False,
        )
        self.ask_result = Answer(
            text="Default answer",
            sources=[_mk_result(file_path="docs/contract.txt")],
            model="stub:model",
            confidence_level="high",
        )
        self.ask_error: Exception | None = None
        self.search_result = [_mk_result(file_path="docs/fallback.txt")]

    def status(self) -> RepoStatus:
        return self.status_value

    def ask(self, question: str, top_k: int = 5) -> Answer:
        self.ask_calls.append(question)
        if self.ask_error:
            raise self.ask_error
        return self.ask_result

    def search(self, question: str, top_k: int = 5):
        self.search_calls.append(question)
        return self.search_result[:top_k]


class _FakeBoltApp:
    def __init__(self) -> None:
        self.event_handlers: dict[str, object] = {}
        self.command_handlers: dict[str, object] = {}

    def event(self, name: str):
        def decorator(handler):
            self.event_handlers[name] = handler
            return handler

        return decorator

    def command(self, name: str):
        def decorator(handler):
            self.command_handlers[name] = handler
            return handler

        return decorator


class _FakeSlackClient:
    def __init__(self, *, email: str = "user@example.com") -> None:
        self.email = email
        self.users_info_exc: Exception | None = None
        self.users_info_calls: list[str] = []
        self.posted_messages: list[dict] = []
        self.posted_ephemeral: list[dict] = []

    def users_info(self, *, user: str):
        self.users_info_calls.append(user)
        if self.users_info_exc is not None:
            raise self.users_info_exc
        return {"user": {"profile": {"email": self.email}}}

    def chat_postMessage(self, **kwargs):
        self.posted_messages.append(kwargs)
        return {"ok": True}

    def chat_postEphemeral(self, **kwargs):
        self.posted_ephemeral.append(kwargs)
        return {"ok": True}


class _RateLimitedClient(_FakeSlackClient):
    def chat_postMessage(self, **kwargs):
        self.posted_messages.append(kwargs)
        if kwargs.get("text") == RATE_LIMIT_EXHAUSTED:
            return {"ok": True}

        exc = RuntimeError("rate limited")
        exc.response = SimpleNamespace(status_code=429, headers={"Retry-After": "0"})
        raise exc


def _mk_result(file_path: str = "docs/file.txt") -> SearchResult:
    return SearchResult(
        file_path=file_path,
        start_line=3,
        end_line=9,
        snippet="payment terms",
        score=1.0,
        scope="section 1",
        chunk_id="chunk-1",
    )


def _manager_and_workspace(tmp_path: Path):
    root = tmp_path / ".codesight"
    manager = WorkspaceManager(db_path=root / "workspaces.db", data_root=root / "data")
    workspace = manager.create("Slack Workspace")
    return manager, workspace


def _service_for_workspace(tmp_path: Path, *, allow_email: str | None = None):
    manager, workspace = _manager_and_workspace(tmp_path)
    if allow_email:
        manager.allow(workspace.id, allow_email)

    engine = _StubEngine()
    service = slack_module._SlackBotService(
        app=_FakeBoltApp(),
        engine=engine,
        workspace_manager=manager,
        workspace_id=workspace.id,
        workspace_name=workspace.name,
    )
    return service, engine, manager, workspace


# SPEC-015-001

def test_spec_015_001_missing_bot_token(monkeypatch: pytest.MonkeyPatch, tmp_path):
    manager, workspace = _manager_and_workspace(tmp_path)
    monkeypatch.delenv("CODESIGHT_SLACK_BOT_TOKEN", raising=False)
    monkeypatch.setenv("CODESIGHT_SLACK_WORKSPACE", workspace.name)
    monkeypatch.setenv("CODESIGHT_SLACK_SIGNING_SECRET", "secret")

    with pytest.raises(RuntimeError) as exc:
        _load_startup_config(manager=manager)

    assert str(exc.value) == MISSING_BOT_TOKEN


def test_spec_015_001_missing_workspace(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CODESIGHT_SLACK_BOT_TOKEN", "xoxb-123")
    monkeypatch.delenv("CODESIGHT_SLACK_WORKSPACE", raising=False)
    monkeypatch.setenv("CODESIGHT_SLACK_SIGNING_SECRET", "secret")

    with pytest.raises(RuntimeError) as exc:
        _load_startup_config()

    assert str(exc.value) == MISSING_WORKSPACE


def test_spec_015_001_nonexistent_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path):
    manager, _ = _manager_and_workspace(tmp_path)
    monkeypatch.setenv("CODESIGHT_SLACK_BOT_TOKEN", "xoxb-123")
    monkeypatch.setenv("CODESIGHT_SLACK_WORKSPACE", "Missing Workspace")
    monkeypatch.setenv("CODESIGHT_SLACK_SIGNING_SECRET", "secret")

    with pytest.raises(RuntimeError) as exc:
        _load_startup_config(manager=manager)

    assert (
        str(exc.value)
        == "Workspace 'Missing Workspace' not found. "
        "Run 'codesight workspace list' to see available workspaces."
    )


def test_spec_015_001_socket_mode_auto_select(monkeypatch: pytest.MonkeyPatch, tmp_path):
    manager, workspace = _manager_and_workspace(tmp_path)
    monkeypatch.setenv("CODESIGHT_SLACK_BOT_TOKEN", "xoxb-123")
    monkeypatch.setenv("CODESIGHT_SLACK_WORKSPACE", workspace.name)
    monkeypatch.setenv("CODESIGHT_SLACK_APP_TOKEN", "xapp-456")
    monkeypatch.delenv("CODESIGHT_SLACK_SIGNING_SECRET", raising=False)

    config = _load_startup_config(manager=manager)

    assert config.mode == "socket"
    assert config.bot_token == "xoxb-123"
    assert config.app_token == "xapp-456"
    assert config.signing_secret is None


def test_spec_015_001_http_missing_signing_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    manager, workspace = _manager_and_workspace(tmp_path)
    monkeypatch.setenv("CODESIGHT_SLACK_BOT_TOKEN", "xoxb-123")
    monkeypatch.setenv("CODESIGHT_SLACK_WORKSPACE", workspace.name)
    monkeypatch.delenv("CODESIGHT_SLACK_APP_TOKEN", raising=False)
    monkeypatch.delenv("CODESIGHT_SLACK_SIGNING_SECRET", raising=False)

    with pytest.raises(RuntimeError) as exc:
        _load_startup_config(manager=manager)

    assert str(exc.value) == MISSING_SIGNING_SECRET


# SPEC-015-003

def test_spec_015_003_strip_mention_prefix():
    assert _strip_mention_prefix("<@U1> <@U2>   What are the payment terms?") == (
        "What are the payment terms?"
    )


def test_spec_015_003_truncate_500_chars():
    question, note = _normalize_question("Q" * 700, from_slash=False, strip_mention=False)

    assert len(question) == 500
    assert note == TRUNCATION_NOTE


def test_spec_015_003_empty_slash_command_usage():
    with pytest.raises(ValueError) as exc:
        _normalize_question("   ", from_slash=True, strip_mention=False)

    assert str(exc.value) == USAGE_SLASH


# SPEC-015-004

def test_spec_015_004_acl_denied_no_engine_call(tmp_path):
    service, engine, _manager, workspace = _service_for_workspace(tmp_path)
    client = _FakeSlackClient(email="denied@example.com")

    service._process_query(
        client=client,
        user_id="U1",
        question="Can I access this?",
        question_note=None,
        channel="C1",
        thread_ts=None,
        ephemeral_user_id=None,
    )

    assert engine.ask_calls == []
    assert engine.search_calls == []
    assert client.posted_messages[0]["text"] == (
        f"You don't have access to workspace '{workspace.name}'. Contact your admin."
    )


def test_spec_015_004_missing_email_scope_message(tmp_path):
    service, engine, manager, workspace = _service_for_workspace(
        tmp_path,
        allow_email="user@example.com",
    )
    assert manager.check_access(workspace.id, "user@example.com") is True

    client = _FakeSlackClient()
    missing_scope_exc = RuntimeError("missing users:read.email")
    missing_scope_exc.response = {"error": "missing_scope", "needed": "users:read.email"}
    client.users_info_exc = missing_scope_exc

    service._process_query(
        client=client,
        user_id="U1",
        question="question",
        question_note=None,
        channel="C1",
        thread_ts=None,
        ephemeral_user_id=None,
    )

    assert client.posted_messages[0]["text"] == MISSING_EMAIL_SCOPE
    assert engine.ask_calls == []
    assert engine.search_calls == []


# SPEC-015-005

def test_spec_015_005_block_kit_high_confidence():
    blocks = answer_blocks(
        answer_text="Answer text",
        confidence_level="high",
        sources=[_mk_result()],
        note=None,
    )

    assert isinstance(blocks, list)
    assert blocks[0]["type"] == "section"
    assert ":large_green_circle: High Confidence" in blocks[0]["text"]["text"]


def test_spec_015_005_block_kit_truncate_3000():
    text, truncated = truncate_answer("A" * 4000)

    assert truncated is True
    assert len(text) == 3000
    assert text.endswith("... (truncated)")


def test_spec_015_005_sources_max_5():
    sources = [_mk_result(file_path=f"docs/file_{i}.txt") for i in range(7)]

    blocks = answer_blocks(
        answer_text="Answer",
        confidence_level="medium",
        sources=sources,
        note=None,
    )

    source_text = blocks[-1]["text"]["text"]
    assert source_text.count("•") == 5


def test_spec_015_005_http_urls_clickable():
    http_line = source_line(_mk_result(file_path="https://example.com/docs/contract.pdf"))
    local_line = source_line(_mk_result(file_path="docs/local-note.md"))

    assert "<https://example.com/docs/contract.pdf|contract.pdf>" in http_line
    assert "`local-note.md`" in local_line


# SPEC-015-006

def test_spec_015_006_dm_direct_reply(tmp_path):
    service, _engine, _manager, _workspace = _service_for_workspace(
        tmp_path,
        allow_email="user@example.com",
    )
    client = _FakeSlackClient(email="user@example.com")

    service._handle_dm_event(
        event={"user": "U1", "channel": "D1", "text": "Summarize this"},
        client=client,
    )

    assert len(client.posted_messages) == 1
    assert client.posted_messages[0]["channel"] == "D1"
    assert "thread_ts" not in client.posted_messages[0]


def test_spec_015_006_mention_threaded_reply(tmp_path):
    service, _engine, _manager, _workspace = _service_for_workspace(
        tmp_path,
        allow_email="user@example.com",
    )
    client = _FakeSlackClient(email="user@example.com")

    service._handle_mention_event(
        event={
            "user": "U1",
            "channel": "C1",
            "text": "<@UBOT> answer this",
            "ts": "1717000000.200",
        },
        client=client,
    )

    assert len(client.posted_messages) == 1
    assert client.posted_messages[0]["thread_ts"] == "1717000000.200"


def test_spec_015_006_slash_ephemeral_default(tmp_path):
    service, _engine, _manager, _workspace = _service_for_workspace(
        tmp_path,
        allow_email="user@example.com",
    )
    client = _FakeSlackClient(email="user@example.com")

    service._handle_slash_command(
        body={
            "user_id": "U1",
            "channel_id": "C1",
            "text": "What changed this week?",
        },
        client=client,
    )

    assert len(client.posted_ephemeral) == 1
    assert client.posted_ephemeral[0]["channel"] == "C1"
    assert client.posted_ephemeral[0]["user"] == "U1"

    service._handle_slash_command(
        body={
            "user_id": "U1",
            "channel_id": "C1",
            "text": "--public What changed this week?",
            "container": {"thread_ts": "1717.99"},
        },
        client=client,
    )

    assert len(client.posted_messages) == 1
    assert client.posted_messages[0]["thread_ts"] == "1717.99"


# SPEC-015-007

def test_spec_015_007_llm_failure_search_fallback(tmp_path):
    service, engine, _manager, _workspace = _service_for_workspace(
        tmp_path,
        allow_email="user@example.com",
    )
    engine.ask_error = RuntimeError("LLM down")
    engine.search_result = [_mk_result(file_path="docs/fallback-hit.md")]
    client = _FakeSlackClient(email="user@example.com")

    service._process_query(
        client=client,
        user_id="U1",
        question="question",
        question_note=None,
        channel="C1",
        thread_ts=None,
        ephemeral_user_id=None,
    )

    assert engine.search_calls == ["question"]
    assert client.posted_messages[0]["text"] == LLM_FALLBACK
    assert LLM_FALLBACK in client.posted_messages[0]["blocks"][0]["text"]["text"]


def test_spec_015_007_empty_index_message(tmp_path):
    service, engine, _manager, workspace = _service_for_workspace(
        tmp_path,
        allow_email="user@example.com",
    )
    engine.status_value = RepoStatus(
        repo_path="/tmp/data",
        indexed=False,
        chunk_count=0,
        files_indexed=0,
        stale=False,
    )
    client = _FakeSlackClient(email="user@example.com")

    service._process_query(
        client=client,
        user_id="U1",
        question="question",
        question_note=None,
        channel="C1",
        thread_ts=None,
        ephemeral_user_id=None,
    )

    assert client.posted_messages[0]["text"] == (
        "I haven't indexed any documents yet. "
        f"Ask your admin to run 'codesight sync --workspace {workspace.name}'."
    )


# EDGE-015

def test_edge_015_001_missing_required_bot_token(monkeypatch: pytest.MonkeyPatch, tmp_path):
    manager, workspace = _manager_and_workspace(tmp_path)
    monkeypatch.delenv("CODESIGHT_SLACK_BOT_TOKEN", raising=False)
    monkeypatch.setenv("CODESIGHT_SLACK_WORKSPACE", workspace.name)
    monkeypatch.setenv("CODESIGHT_SLACK_SIGNING_SECRET", "secret")

    with pytest.raises(RuntimeError) as exc:
        _load_startup_config(manager=manager)

    assert str(exc.value) == MISSING_BOT_TOKEN


def test_edge_015_002_missing_workspace_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CODESIGHT_SLACK_BOT_TOKEN", "xoxb-123")
    monkeypatch.delenv("CODESIGHT_SLACK_WORKSPACE", raising=False)
    monkeypatch.setenv("CODESIGHT_SLACK_SIGNING_SECRET", "secret")

    with pytest.raises(RuntimeError) as exc:
        _load_startup_config()

    assert str(exc.value) == MISSING_WORKSPACE


def test_edge_015_003_workspace_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path):
    manager, _ = _manager_and_workspace(tmp_path)
    monkeypatch.setenv("CODESIGHT_SLACK_BOT_TOKEN", "xoxb-123")
    monkeypatch.setenv("CODESIGHT_SLACK_WORKSPACE", "does-not-exist")
    monkeypatch.setenv("CODESIGHT_SLACK_SIGNING_SECRET", "secret")

    with pytest.raises(RuntimeError) as exc:
        _load_startup_config(manager=manager)

    assert (
        str(exc.value)
        == "Workspace 'does-not-exist' not found. "
        "Run 'codesight workspace list' to see available workspaces."
    )


def test_edge_015_004_missing_email_scope(tmp_path):
    service, _engine, _manager, _workspace = _service_for_workspace(
        tmp_path,
        allow_email="user@example.com",
    )
    client = _FakeSlackClient()
    missing_scope_exc = RuntimeError("missing users:read.email")
    missing_scope_exc.response = {"error": "missing_scope", "needed": "users:read.email"}
    client.users_info_exc = missing_scope_exc

    service._process_query(
        client=client,
        user_id="U1",
        question="question",
        question_note=None,
        channel="C1",
        thread_ts=None,
        ephemeral_user_id=None,
    )

    assert client.posted_messages[0]["text"] == MISSING_EMAIL_SCOPE


def test_edge_015_005_acl_denied_user(tmp_path):
    service, engine, _manager, workspace = _service_for_workspace(tmp_path)
    client = _FakeSlackClient(email="denied@example.com")

    service._process_query(
        client=client,
        user_id="U2",
        question="question",
        question_note=None,
        channel="C2",
        thread_ts=None,
        ephemeral_user_id=None,
    )

    assert client.posted_messages[0]["text"] == (
        f"You don't have access to workspace '{workspace.name}'. Contact your admin."
    )
    assert engine.ask_calls == []
    assert engine.search_calls == []


def test_edge_015_006_question_exceeds_limit(tmp_path):
    service, engine, _manager, _workspace = _service_for_workspace(
        tmp_path,
        allow_email="user@example.com",
    )
    client = _FakeSlackClient(email="user@example.com")

    service._handle_dm_event(
        event={"user": "U1", "channel": "D1", "text": "Q" * 700},
        client=client,
    )

    assert len(engine.ask_calls[0]) == 500
    assert client.posted_messages[0]["blocks"][2]["elements"][0]["text"] == TRUNCATION_NOTE


def test_edge_015_007_empty_workspace_index(tmp_path):
    service, engine, _manager, workspace = _service_for_workspace(
        tmp_path,
        allow_email="user@example.com",
    )
    engine.status_value = RepoStatus(
        repo_path="/tmp/data",
        indexed=False,
        chunk_count=0,
        files_indexed=0,
        stale=False,
    )
    client = _FakeSlackClient(email="user@example.com")

    service._process_query(
        client=client,
        user_id="U1",
        question="question",
        question_note=None,
        channel="C1",
        thread_ts=None,
        ephemeral_user_id=None,
    )

    assert client.posted_messages[0]["text"] == (
        "I haven't indexed any documents yet. "
        f"Ask your admin to run 'codesight sync --workspace {workspace.name}'."
    )


def test_edge_015_008_slack_rate_limit_exceeded(tmp_path, monkeypatch: pytest.MonkeyPatch):
    service, _engine, _manager, _workspace = _service_for_workspace(
        tmp_path,
        allow_email="user@example.com",
    )
    client = _RateLimitedClient(email="user@example.com")

    monotonic_values = iter([0.0, 0.01, 0.2, 0.3])
    monkeypatch.setattr(slack_module, "_RETRY_BUDGET_SECONDS", 0.15)
    monkeypatch.setattr(
        slack_module.time,
        "monotonic",
        lambda: next(monotonic_values, 0.3),
    )
    monkeypatch.setattr(slack_module.time, "sleep", lambda _seconds: None)

    posted = service._post_message(
        client=client,
        user_id="U1",
        channel="C1",
        text="result",
        blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "result"}}],
        thread_ts=None,
        ephemeral_user_id=None,
    )

    assert posted is False
    assert len(client.posted_messages) >= 2
    assert client.posted_messages[-1]["text"] == RATE_LIMIT_EXHAUSTED

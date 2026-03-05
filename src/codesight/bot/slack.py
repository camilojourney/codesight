"""Slack bot integration built on Bolt for Python."""

from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from ..api import CodeSight
from ..workspace import WorkspaceManager
from .blocks import (
    answer_blocks,
    error_blocks,
    no_index_blocks,
    search_fallback_blocks,
    truncate_answer,
)

try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    from slack_bolt.request import BoltRequest
    from slack_sdk.errors import SlackApiError
except ImportError:  # pragma: no cover - optional dependency path
    App = None
    SocketModeHandler = None
    BoltRequest = None

    class SlackApiError(Exception):  # type: ignore[no-redef]
        """Fallback Slack API error type for dependency-missing runtimes."""


logger = logging.getLogger(__name__)

_QUESTION_LIMIT = 500
_QUESTION_LOG_LIMIT = 50
_RETRY_BUDGET_SECONDS = 30.0

MISSING_BOT_TOKEN = "CODESIGHT_SLACK_BOT_TOKEN is required."
MISSING_WORKSPACE = "CODESIGHT_SLACK_WORKSPACE is required."
MISSING_SIGNING_SECRET = "CODESIGHT_SLACK_SIGNING_SECRET is required in HTTP mode."
MISSING_EMAIL_SCOPE = "Bot is missing Slack scope 'users:read.email'. Contact your admin."
USAGE_SLASH = "Usage: /codesight <your question>"
NON_TEXT_ERROR = "Please send a text question, for example: What are the payment terms?"
TRUNCATION_NOTE = "Note: your question was truncated to 500 characters."
LLM_FALLBACK = (
    "I'm having trouble connecting to the AI service. "
    "Here are the most relevant documents:"
)
RATE_LIMIT_EXHAUSTED = "Slack is rate limiting responses right now. Please retry in a few seconds."


@dataclass(frozen=True)
class StartupConfig:
    mode: str
    bot_token: str
    workspace_id: str
    workspace_name: str
    app_token: str | None = None
    signing_secret: str | None = None


class _MissingEmailScopeError(RuntimeError):
    pass


def _require_slack_dependencies() -> None:
    # // EDGE-015-001: Startup hard-fails with dependency guidance when Slack deps are absent.
    if App is None or SocketModeHandler is None or BoltRequest is None:
        raise RuntimeError(
            "Slack bot support requires optional dependency group 'slack' "
            "(install with: pip install -e '.[slack]')."
        )


# // SPEC-015-001: Env validation enforces required vars and startup mode selection.
def _load_startup_config(*, manager: WorkspaceManager | None = None) -> StartupConfig:
    bot_token = os.environ.get("CODESIGHT_SLACK_BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError(MISSING_BOT_TOKEN)

    workspace_name = os.environ.get("CODESIGHT_SLACK_WORKSPACE", "").strip()
    if not workspace_name:
        raise RuntimeError(MISSING_WORKSPACE)

    manager = manager or WorkspaceManager()
    try:
        workspace = manager.get(workspace_name)
    except Exception as exc:
        message = (
            f"Workspace '{workspace_name}' not found. "
            "Run 'codesight workspace list' to see available workspaces."
        )
        raise RuntimeError(message) from exc

    app_token = os.environ.get("CODESIGHT_SLACK_APP_TOKEN", "").strip() or None
    if app_token:
        return StartupConfig(
            mode="socket",
            bot_token=bot_token,
            app_token=app_token,
            workspace_id=workspace.id,
            workspace_name=workspace.name,
        )

    signing_secret = os.environ.get("CODESIGHT_SLACK_SIGNING_SECRET", "").strip()
    if not signing_secret:
        raise RuntimeError(MISSING_SIGNING_SECRET)

    return StartupConfig(
        mode="http",
        bot_token=bot_token,
        signing_secret=signing_secret,
        workspace_id=workspace.id,
        workspace_name=workspace.name,
    )


def _question_preview(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized[:_QUESTION_LOG_LIMIT]


def _strip_mention_prefix(text: str) -> str:
    return re.sub(r"^(?:<@[^>]+>\s*)+", "", text or "").strip()


def _normalize_question(
    raw_text: str,
    *,
    from_slash: bool,
    strip_mention: bool,
) -> tuple[str, str | None]:
    text = raw_text or ""
    if strip_mention:
        text = _strip_mention_prefix(text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise ValueError(USAGE_SLASH if from_slash else NON_TEXT_ERROR)
    if len(text) <= _QUESTION_LIMIT:
        return text, None
    return text[:_QUESTION_LIMIT], TRUNCATION_NOTE


def _parse_slash_text(text: str) -> tuple[bool, str]:
    payload = (text or "").strip()
    if payload.startswith("--public"):
        return True, payload[len("--public") :].strip()
    return False, payload


def _slack_response_get(response: Any, key: str, default: Any = None) -> Any:
    if response is None:
        return default
    if isinstance(response, dict):
        return response.get(key, default)
    if hasattr(response, "get"):
        try:
            return response.get(key, default)
        except Exception:
            pass
    try:
        return response[key]
    except Exception:
        return default


def _is_missing_email_scope_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    error = _slack_response_get(response, "error", "")
    needed = _slack_response_get(response, "needed", "")
    if "users:read.email" in str(needed):
        return True
    if error in {"missing_scope", "invalid_auth", "not_allowed_token_type"}:
        return True
    return "users:read.email" in str(exc)


def _is_rate_limit_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code == 429:
        return True
    error = _slack_response_get(response, "error", "")
    if str(error).lower() in {"ratelimited", "rate_limited"}:
        return True
    return "429" in str(exc) or "rate limit" in str(exc).lower()


def _retry_after_seconds(exc: Exception) -> float:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    retry_after = None
    if isinstance(headers, dict):
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
    if retry_after is None and hasattr(headers, "get"):
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
    try:
        return float(retry_after)
    except (TypeError, ValueError):
        return 0.0


class _SlackBotService:
    def __init__(
        self,
        *,
        app: Any,
        engine: CodeSight,
        workspace_manager: WorkspaceManager,
        workspace_id: str,
        workspace_name: str,
    ) -> None:
        self.app = app
        self.engine = engine
        self.workspace_manager = workspace_manager
        self.workspace_id = workspace_id
        self.workspace_name = workspace_name
        self.executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="codesight-slack")

    def register_handlers(self) -> None:
        # // SPEC-015-002: app_mention events are accepted and processed asynchronously after ack.
        @self.app.event("app_mention")
        def handle_app_mention(event: dict[str, Any], client: Any) -> None:
            logger.info(
                "slack.event.received event_type=app_mention channel_type=%s user_id=%s",
                event.get("channel_type", "channel"),
                event.get("user", ""),
            )
            self.executor.submit(self._handle_mention_event, event=event, client=client)

        # // SPEC-015-002: message events are restricted to DMs and ignored for non-DM channels.
        @self.app.event("message")
        def handle_message(event: dict[str, Any], client: Any) -> None:
            if event.get("channel_type") != "im":
                # // SPEC-015-006: Channel messages without mention receive no response.
                return
            if event.get("subtype"):
                return
            logger.info(
                "slack.event.received event_type=message channel_type=im user_id=%s",
                event.get("user", ""),
            )
            self.executor.submit(self._handle_dm_event, event=event, client=client)

        # // SPEC-015-002: Slash command is acked immediately and then processed asynchronously.
        @self.app.command("/codesight")
        def handle_command(ack: Any, body: dict[str, Any], client: Any) -> None:
            ack()
            logger.info(
                "slack.event.received event_type=slash_command channel_type=%s user_id=%s",
                body.get("channel_name", ""),
                body.get("user_id", ""),
            )
            self.executor.submit(self._handle_slash_command, body=body, client=client)

    def _handle_mention_event(self, *, event: dict[str, Any], client: Any) -> None:
        user_id = str(event.get("user") or "")
        channel = str(event.get("channel") or "")
        if not user_id or not channel:
            return

        try:
            question, note = _normalize_question(
                str(event.get("text") or ""),
                from_slash=False,
                strip_mention=True,
            )
        except ValueError as exc:
            self._post_message(
                client=client,
                user_id=user_id,
                channel=channel,
                text=str(exc),
                blocks=error_blocks(str(exc)),
                thread_ts=str(event.get("ts") or "") or None,
            )
            return

        self._process_query(
            client=client,
            user_id=user_id,
            question=question,
            question_note=note,
            channel=channel,
            thread_ts=str(event.get("ts") or "") or None,
            ephemeral_user_id=None,
        )

    def _handle_dm_event(self, *, event: dict[str, Any], client: Any) -> None:
        user_id = str(event.get("user") or "")
        channel = str(event.get("channel") or "")
        if not user_id or not channel:
            return

        try:
            question, note = _normalize_question(
                str(event.get("text") or ""),
                from_slash=False,
                strip_mention=False,
            )
        except ValueError as exc:
            self._post_message(
                client=client,
                user_id=user_id,
                channel=channel,
                text=str(exc),
                blocks=error_blocks(str(exc)),
                thread_ts=None,
            )
            return

        self._process_query(
            client=client,
            user_id=user_id,
            question=question,
            question_note=note,
            channel=channel,
            thread_ts=None,
            ephemeral_user_id=None,
        )

    def _handle_slash_command(self, *, body: dict[str, Any], client: Any) -> None:
        user_id = str(body.get("user_id") or "")
        channel = str(body.get("channel_id") or "")
        if not user_id or not channel:
            return

        is_public, raw_question = _parse_slash_text(str(body.get("text") or ""))
        try:
            question, note = _normalize_question(
                raw_question,
                from_slash=True,
                strip_mention=False,
            )
        except ValueError as exc:
            self._post_message(
                client=client,
                user_id=user_id,
                channel=channel,
                text=str(exc),
                blocks=error_blocks(str(exc)),
                thread_ts=None,
                ephemeral_user_id=user_id,
            )
            return

        container = body.get("container", {}) if isinstance(body.get("container"), dict) else {}
        thread_ts = (
            str(container.get("thread_ts") or "")
            or str(container.get("message_ts") or "")
            or str(body.get("thread_ts") or "")
            or None
        )
        self._process_query(
            client=client,
            user_id=user_id,
            question=question,
            question_note=note,
            channel=channel,
            thread_ts=thread_ts if is_public else None,
            ephemeral_user_id=None if is_public else user_id,
        )

    def _process_query(
        self,
        *,
        client: Any,
        user_id: str,
        question: str,
        question_note: str | None,
        channel: str,
        thread_ts: str | None,
        ephemeral_user_id: str | None,
    ) -> None:
        logger.info(
            "slack.query.received user_id=%s question=%s",
            user_id,
            _question_preview(question),
        )

        try:
            caller_email = self._resolve_user_email(client, user_id=user_id)
        except _MissingEmailScopeError:
            self._post_message(
                client=client,
                user_id=user_id,
                channel=channel,
                text=MISSING_EMAIL_SCOPE,
                blocks=error_blocks(MISSING_EMAIL_SCOPE),
                thread_ts=thread_ts,
                ephemeral_user_id=ephemeral_user_id,
            )
            return
        except Exception:
            logger.exception("slack.error error_type=email_lookup user_id=%s", user_id)
            self._post_message(
                client=client,
                user_id=user_id,
                channel=channel,
                text="Unable to verify your access right now. Please try again.",
                blocks=error_blocks("Unable to verify your access right now. Please try again."),
                thread_ts=thread_ts,
                ephemeral_user_id=ephemeral_user_id,
            )
            return

        # // SPEC-015-004: ACL check gates all query execution paths.
        if not self.workspace_manager.check_access(self.workspace_id, caller_email):
            message = (
                f"You don't have access to workspace '{self.workspace_name}'. "
                "Contact your admin."
            )
            logger.info("slack.query.denied workspace_id=%s user_id=%s", self.workspace_id, user_id)
            self._post_message(
                client=client,
                user_id=user_id,
                channel=channel,
                text=message,
                blocks=error_blocks(message),
                thread_ts=thread_ts,
                ephemeral_user_id=ephemeral_user_id,
            )
            return

        logger.info("slack.query.allowed workspace_id=%s user_id=%s", self.workspace_id, user_id)

        status = self.engine.status()
        if not status.indexed or status.chunk_count == 0:
            self._post_message(
                client=client,
                user_id=user_id,
                channel=channel,
                text=no_index_blocks(self.workspace_name)[0]["text"]["text"],
                blocks=no_index_blocks(self.workspace_name),
                thread_ts=thread_ts,
                ephemeral_user_id=ephemeral_user_id,
            )
            return

        started = time.monotonic()
        try:
            answer = self.engine.ask(question, top_k=5)
            truncated_answer_text, _ = truncate_answer(answer.text)
            blocks = answer_blocks(
                answer_text=answer.text,
                confidence_level=answer.confidence_level,
                sources=answer.sources,
                note=question_note,
            )
            sent = self._post_message(
                client=client,
                user_id=user_id,
                channel=channel,
                text=truncated_answer_text,
                blocks=blocks,
                thread_ts=thread_ts,
                ephemeral_user_id=ephemeral_user_id,
            )
            if sent:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                logger.info(
                    "slack.answer.sent confidence=%s latency_ms=%d user_id=%s",
                    answer.confidence_level,
                    elapsed_ms,
                    user_id,
                )
            return
        except Exception:
            # // EDGE-015-007: ask() failures fall back to search() source list response.
            logger.exception("slack.error error_type=ask_failed user_id=%s", user_id)

        fallback_results: list[Any] = []
        try:
            fallback_results = self.engine.search(question, top_k=5)
        except Exception:
            logger.exception("slack.error error_type=search_fallback_failed user_id=%s", user_id)

        self._post_message(
            client=client,
            user_id=user_id,
            channel=channel,
            text=LLM_FALLBACK,
            blocks=search_fallback_blocks(LLM_FALLBACK, fallback_results, note=question_note),
            thread_ts=thread_ts,
            ephemeral_user_id=ephemeral_user_id,
        )

    def _resolve_user_email(self, client: Any, *, user_id: str) -> str:
        try:
            response = client.users_info(user=user_id)
        except Exception as exc:
            # // EDGE-015-004: Missing users:read.email scope returns deterministic admin message.
            if _is_missing_email_scope_error(exc):
                raise _MissingEmailScopeError from exc
            raise

        profile = _slack_response_get(_slack_response_get(response, "user", {}), "profile", {})
        email = _slack_response_get(profile, "email", "")
        if not email:
            raise _MissingEmailScopeError(MISSING_EMAIL_SCOPE)
        return str(email)

    def _post_message(
        self,
        *,
        client: Any,
        user_id: str,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]],
        thread_ts: str | None,
        ephemeral_user_id: str | None = None,
    ) -> bool:
        payload: dict[str, Any] = {
            "channel": channel,
            "text": text,
            "blocks": blocks,
        }
        if thread_ts:
            payload["thread_ts"] = thread_ts

        if ephemeral_user_id:
            payload["user"] = ephemeral_user_id
            post_fn = client.chat_postEphemeral
        else:
            post_fn = client.chat_postMessage

        exhausted_notice = {
            "channel": channel,
            "text": RATE_LIMIT_EXHAUSTED,
            "user": ephemeral_user_id,
        }
        if thread_ts and ephemeral_user_id is None:
            exhausted_notice["thread_ts"] = thread_ts
        if ephemeral_user_id is None:
            exhausted_notice.pop("user", None)

        return self._post_with_retry(
            post_fn=post_fn,
            payload=payload,
            exhausted_notice=exhausted_notice,
            user_id=user_id,
        )

    # // EDGE-015-008: Slack rate limits trigger bounded exponential backoff up to 30 seconds.
    def _post_with_retry(
        self,
        *,
        post_fn: Any,
        payload: dict[str, Any],
        exhausted_notice: dict[str, Any],
        user_id: str,
    ) -> bool:
        deadline = time.monotonic() + _RETRY_BUDGET_SECONDS
        backoff = 1.0

        while True:
            try:
                post_fn(**payload)
                return True
            except Exception as exc:
                if _is_rate_limit_error(exc):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    retry_after = _retry_after_seconds(exc)
                    wait_seconds = max(backoff, retry_after, 0.1)
                    wait_seconds = min(wait_seconds, remaining)
                    logger.warning(
                        "slack.rate_limit.hit user_id=%s retry_in_seconds=%.2f",
                        user_id,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    backoff = min(backoff * 2, 8.0)
                    continue

                logger.exception("slack.error error_type=reply_failed user_id=%s", user_id)
                return False

        try:
            post_fn(**exhausted_notice)
        except Exception:
            logger.exception("slack.error error_type=rate_limit_notice_failed user_id=%s", user_id)

        logger.error("slack.error error_type=rate_limit_exhausted user_id=%s", user_id)
        return False


# // SPEC-015-001: Slack app creation validates startup config and preloads workspace engine.
def create_slack_app(
    *,
    workspace_manager: WorkspaceManager | None = None,
    engine: CodeSight | None = None,
    startup_config: StartupConfig | None = None,
) -> Any:
    _require_slack_dependencies()
    assert App is not None

    manager = workspace_manager or WorkspaceManager()
    config = startup_config or _load_startup_config(manager=manager)
    if engine is None:
        engine = CodeSight(workspace=config.workspace_name)

    if config.mode == "socket":
        app = App(token=config.bot_token)
    else:
        app = App(token=config.bot_token, signing_secret=config.signing_secret)

    service = _SlackBotService(
        app=app,
        engine=engine,
        workspace_manager=manager,
        workspace_id=config.workspace_id,
        workspace_name=config.workspace_name,
    )
    service.register_handlers()
    setattr(app, "_codesight_slack_service", service)
    setattr(app, "_codesight_startup_config", config)
    return app


def _make_http_handler(app: Any):
    assert BoltRequest is not None

    class _SlackHTTPHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path not in {"/slack/events", "/slack/commands"}:
                self.send_response(404)
                self.end_headers()
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8")
            headers = {key: value for key, value in self.headers.items()}
            request = BoltRequest(body=body, headers=headers)
            response = app.dispatch(request)

            # // SPEC-015-002: Invalid Slack signatures surface as 401 responses.
            if response.status == 401:
                logger.warning("slack.error error_type=invalid_signature status=401")

            self.send_response(response.status)
            for key, value in (response.headers or {}).items():
                if value is None:
                    continue
                self.send_header(key, str(value))
            self.end_headers()

            raw_body = response.body or ""
            if isinstance(raw_body, bytes):
                self.wfile.write(raw_body)
            else:
                self.wfile.write(str(raw_body).encode("utf-8"))

        def log_message(self, _format: str, *args: Any) -> None:  # noqa: A003
            logger.debug("slack.http %s", " ".join(str(arg) for arg in args))

    return _SlackHTTPHandler


# // SPEC-015-001: Runtime starts in socket or HTTP mode based on startup env configuration.
def run_slack_bot(*, host: str = "0.0.0.0", port: int = 3000) -> None:
    _require_slack_dependencies()
    assert SocketModeHandler is not None

    config = _load_startup_config()
    app = create_slack_app(startup_config=config)

    if config.mode == "socket":
        logger.info("slack.mode.selected mode=socket workspace_id=%s", config.workspace_id)
        SocketModeHandler(app, config.app_token).start()
        return

    logger.info("slack.mode.selected mode=http workspace_id=%s", config.workspace_id)
    handler = _make_http_handler(app)
    server = ThreadingHTTPServer((host, port), handler)
    logger.info("slack.http.start host=%s port=%d", host, port)
    server.serve_forever()

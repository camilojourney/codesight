"""Block Kit builders for Slack bot responses."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

MAX_ANSWER_CHARS = 3000
MAX_SOURCE_COUNT = 5

CONFIDENCE_LABELS = {
    "high": ":large_green_circle: High Confidence",
    "medium": ":large_yellow_circle: Medium Confidence",
    "low": ":red_circle: Low Confidence",
    "refused": ":black_circle: No Answer Found",
}


# // SPEC-015-005: Confidence values are rendered using fixed Slack emoji labels.
def confidence_label(confidence_level: str) -> str:
    return CONFIDENCE_LABELS.get(confidence_level, CONFIDENCE_LABELS["low"])


# // SPEC-015-005: Answer text is capped at 3000 chars with deterministic truncation suffix.
def truncate_answer(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_ANSWER_CHARS:
        return text, False
    suffix = "... (truncated)"
    return f"{text[: MAX_ANSWER_CHARS - len(suffix)]}{suffix}", True


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}


def _source_label(path_value: str) -> str:
    if _is_http_url(path_value):
        parsed = urlparse(path_value)
        candidate = Path(parsed.path).name or parsed.netloc
        return candidate or path_value
    return Path(path_value).name or path_value


# // SPEC-015-005: Sources include file label plus start/end page-or-line range.
def source_line(source: Any) -> str:
    file_path = getattr(source, "file_path", "unknown")
    start_line = getattr(source, "start_line", "?")
    end_line = getattr(source, "end_line", "?")
    scope = getattr(source, "scope", "")
    range_label = f"{start_line}-{end_line}"
    label = _source_label(file_path)
    display = f"<{file_path}|{label}>" if _is_http_url(file_path) else f"`{label}`"
    scope_suffix = f" - {scope}" if scope else ""
    return f"• {display} ({range_label}){scope_suffix}"


# // SPEC-015-005: Successful answer payloads render confidence, answer, and up to 5 sources.
def answer_blocks(
    *,
    answer_text: str,
    confidence_level: str,
    sources: list[Any],
    note: str | None = None,
) -> list[dict[str, Any]]:
    truncated_answer, _ = truncate_answer(answer_text)
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{confidence_label(confidence_level)}*"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": truncated_answer or "_No answer text returned._"},
        },
    ]
    if note:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": note}]})

    visible_sources = sources[:MAX_SOURCE_COUNT]
    source_lines = [source_line(item) for item in visible_sources]
    source_text = "\n".join(source_lines) if source_lines else "_No sources available._"
    blocks.append(
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Sources*\n{source_text}"}}
    )
    return blocks

# // SPEC-015-005: Backward-compatible alias for callers expecting build_* naming.
def build_answer_blocks(
    *,
    answer_text: str,
    confidence_level: str,
    sources: list[Any],
    note: str | None = None,
) -> list[dict[str, Any]]:
    return answer_blocks(
        answer_text=answer_text,
        confidence_level=confidence_level,
        sources=sources,
        note=note,
    )


# // EDGE-015-007: Empty-index responses are explicit setup guidance for admins.
def no_index_blocks(workspace_name: str) -> list[dict[str, Any]]:
    message = (
        "I haven't indexed any documents yet. Ask your admin to run "
        f"'codesight sync --workspace {workspace_name}'."
    )
    return error_blocks(message)


def error_blocks(message: str) -> list[dict[str, Any]]:
    return [{"type": "section", "text": {"type": "mrkdwn", "text": message}}]


# // EDGE-015-002: LLM failure falls back to ranked search results rendered in Block Kit.
def search_fallback_blocks(
    message: str,
    results: list[Any],
    note: str | None = None,
) -> list[dict[str, Any]]:
    visible_sources = results[:MAX_SOURCE_COUNT]
    lines = [source_line(item) for item in visible_sources]
    body = message if not lines else f"{message}\n\n" + "\n".join(lines)
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": body}}]
    if note:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": note}]})
    return blocks

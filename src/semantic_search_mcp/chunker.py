"""Language-aware code chunking with scope-delimited splits.

Phase 1 strategy: regex-based splitting on top-level function/class boundaries,
with context headers prepended to improve embedding quality.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import DEFAULT_CHUNK_MAX_LINES, DEFAULT_CHUNK_OVERLAP_LINES


# ---------------------------------------------------------------------------
# Language-specific boundary patterns
# ---------------------------------------------------------------------------

# Each pattern matches the START of a new top-level scope
_BOUNDARY_PATTERNS: dict[str, re.Pattern] = {
    "python": re.compile(r"^(class |def |async def )", re.MULTILINE),
    "javascript": re.compile(
        r"^(export\s+)?(function |class |const \w+ = |let \w+ = |var \w+ = )", re.MULTILINE
    ),
    "typescript": re.compile(
        r"^(export\s+)?(function |class |const \w+ = |let \w+ = |interface |type |enum )",
        re.MULTILINE,
    ),
    "go": re.compile(r"^(func |type )", re.MULTILINE),
    "rust": re.compile(r"^(pub\s+)?(fn |struct |enum |impl |trait |mod )", re.MULTILINE),
    "java": re.compile(
        r"^(public |private |protected )?(static )?(class |interface |enum |void |int |String )",
        re.MULTILINE,
    ),
    "ruby": re.compile(r"^(class |module |def )", re.MULTILINE),
    "php": re.compile(r"^(class |function |public |private |protected )", re.MULTILINE),
    "c": re.compile(r"^(\w+\s+\*?\w+\s*\()", re.MULTILINE),
    "cpp": re.compile(r"^(class |struct |namespace |template |(\w+\s+\*?\w+\s*\())", re.MULTILINE),
}

# Map file extension to language key
_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java", ".kt": "java", ".scala": "java",
    ".rb": "ruby", ".rake": "ruby",
    ".php": "php",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".hpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".cs": "java",  # close enough for boundary detection
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Chunk:
    """A single chunk of source code with metadata."""

    file_path: str  # relative to repo root
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed, inclusive
    content: str  # raw code
    scope: str  # e.g. "function validate_token" or "class JWTValidator"
    language: str
    context_header: str  # prepended before embedding
    content_hash: str = field(init=False)

    def __post_init__(self):
        self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()[:16]

    @property
    def embedding_text(self) -> str:
        """Text sent to the embedding model (context header + code)."""
        return f"{self.context_header}\n{self.content}"

    @property
    def chunk_id(self) -> str:
        """Unique ID: file + line range + hash."""
        return f"{self.file_path}:{self.start_line}-{self.end_line}:{self.content_hash}"


# ---------------------------------------------------------------------------
# Scope detection helpers
# ---------------------------------------------------------------------------


def _detect_scope(first_line: str, language: str) -> str:
    """Extract a human-readable scope label from the first line of a chunk."""
    first_line = first_line.strip()
    if not first_line:
        return "module-level"

    # Python: "def foo(...)" → "function foo"
    if language == "python":
        m = re.match(r"(async\s+)?def\s+(\w+)", first_line)
        if m:
            return f"function {m.group(2)}"
        m = re.match(r"class\s+(\w+)", first_line)
        if m:
            return f"class {m.group(1)}"

    # JS/TS
    if language in ("javascript", "typescript"):
        m = re.match(r"(?:export\s+)?function\s+(\w+)", first_line)
        if m:
            return f"function {m.group(1)}"
        m = re.match(r"(?:export\s+)?class\s+(\w+)", first_line)
        if m:
            return f"class {m.group(1)}"
        m = re.match(r"(?:export\s+)?(?:const|let|var)\s+(\w+)", first_line)
        if m:
            return f"const {m.group(1)}"

    # Go
    if language == "go":
        m = re.match(r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)", first_line)
        if m:
            return f"function {m.group(1)}"
        m = re.match(r"type\s+(\w+)", first_line)
        if m:
            return f"type {m.group(1)}"

    # Rust
    if language == "rust":
        m = re.match(r"(?:pub\s+)?fn\s+(\w+)", first_line)
        if m:
            return f"function {m.group(1)}"
        m = re.match(r"(?:pub\s+)?struct\s+(\w+)", first_line)
        if m:
            return f"struct {m.group(1)}"
        m = re.match(r"(?:pub\s+)?impl\s+(\w+)", first_line)
        if m:
            return f"impl {m.group(1)}"

    # Fallback: use the first significant token
    tokens = first_line.split()
    if tokens:
        return tokens[0]
    return "unknown"


def _make_context_header(file_path: str, scope: str, start_line: int, end_line: int) -> str:
    """Build the context header prepended to chunks before embedding."""
    return f"# File: {file_path}\n# Scope: {scope}\n# Lines: {start_line}-{end_line}"


# ---------------------------------------------------------------------------
# Main chunking logic
# ---------------------------------------------------------------------------


def _detect_language(file_path: str) -> str:
    """Detect language from file extension."""
    ext = Path(file_path).suffix.lower()
    return _EXT_TO_LANG.get(ext, "unknown")


def chunk_file(
    content: str,
    file_path: str,
    max_lines: int = DEFAULT_CHUNK_MAX_LINES,
    overlap_lines: int = DEFAULT_CHUNK_OVERLAP_LINES,
) -> list[Chunk]:
    """Split a file's content into scope-delimited chunks.

    Strategy:
    1. If we have a language-specific boundary pattern, split on those boundaries.
    2. Each split becomes a chunk (unless it exceeds max_lines, in which case
       we sub-split with overlapping windows).
    3. If no pattern is available, fall back to overlapping windows.
    """
    if not content.strip():
        return []

    lines = content.split("\n")
    language = _detect_language(file_path)
    pattern = _BOUNDARY_PATTERNS.get(language)

    if pattern:
        chunks = _split_by_boundaries(lines, file_path, language, pattern, max_lines, overlap_lines)
    else:
        chunks = _split_by_windows(lines, file_path, language, max_lines, overlap_lines)

    return chunks


def _split_by_boundaries(
    lines: list[str],
    file_path: str,
    language: str,
    pattern: re.Pattern,
    max_lines: int,
    overlap_lines: int,
) -> list[Chunk]:
    """Split on regex-detected scope boundaries."""
    # Find all boundary line indices
    boundary_indices = [0]  # always start at line 0
    for i, line in enumerate(lines):
        if i == 0:
            continue
        if pattern.match(line):
            boundary_indices.append(i)

    chunks: list[Chunk] = []
    for idx, start in enumerate(boundary_indices):
        end = boundary_indices[idx + 1] if idx + 1 < len(boundary_indices) else len(lines)
        segment_lines = lines[start:end]

        if len(segment_lines) <= max_lines:
            scope = _detect_scope(segment_lines[0] if segment_lines else "", language)
            header = _make_context_header(file_path, scope, start + 1, end)
            chunk_content = "\n".join(segment_lines)
            chunks.append(Chunk(
                file_path=file_path,
                start_line=start + 1,
                end_line=end,
                content=chunk_content,
                scope=scope,
                language=language,
                context_header=header,
            ))
        else:
            # Sub-split large scopes with overlapping windows
            sub_chunks = _split_by_windows(
                segment_lines, file_path, language, max_lines, overlap_lines,
                line_offset=start,
            )
            chunks.extend(sub_chunks)

    return chunks


def _split_by_windows(
    lines: list[str],
    file_path: str,
    language: str,
    max_lines: int,
    overlap_lines: int,
    line_offset: int = 0,
) -> list[Chunk]:
    """Fall back to fixed-size overlapping windows."""
    chunks: list[Chunk] = []
    i = 0
    while i < len(lines):
        end = min(i + max_lines, len(lines))
        segment = lines[i:end]
        scope = _detect_scope(segment[0] if segment else "", language)
        start_line = line_offset + i + 1
        end_line = line_offset + end
        header = _make_context_header(file_path, scope, start_line, end_line)
        chunks.append(Chunk(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content="\n".join(segment),
            scope=scope,
            language=language,
            context_header=header,
        ))
        i += max_lines - overlap_lines
        if i >= len(lines):
            break

    return chunks

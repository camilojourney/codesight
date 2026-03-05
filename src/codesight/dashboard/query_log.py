"""Query log store and analytics helpers for dashboard metrics."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_QUERY_LOG_PATH = Path.home() / ".codesight" / "query_log.db"
VALID_CONFIDENCE = ("high", "medium", "low", "refused")


@dataclass(slots=True)
class QueryAggregate:
    query_text: str
    frequency: int


@dataclass(slots=True)
class ConfidenceBucket:
    label: str
    count: int
    percentage: float


class QueryLogDB:
    """SQLite-backed query analytics source of truth."""

    # // SPEC-014-008: Dashboard analytics auto-creates query_log schema when missing.
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_QUERY_LOG_PATH).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._bootstrap()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _bootstrap(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_log (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NULL,
                    query_text TEXT NOT NULL,
                    confidence TEXT NOT NULL
                        CHECK(confidence IN ('high', 'medium', 'low', 'refused')),
                    latency_ms INTEGER NOT NULL,
                    source_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_query_log_created
                    ON query_log(created_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_query_log_workspace_created
                    ON query_log(workspace_id, created_at)
                """
            )
            conn.commit()

    # // SPEC-014-008: Query log inserts are parameterized and schema-aligned.
    def log_query(
        self,
        *,
        query_text: str,
        confidence: str,
        latency_ms: int,
        source_count: int,
        workspace_id: str | None = None,
        created_at: str | None = None,
    ) -> None:
        normalized_confidence = confidence.strip().lower()
        if normalized_confidence not in VALID_CONFIDENCE:
            normalized_confidence = "low"

        timestamp = created_at or datetime.now(timezone.utc).isoformat()
        text = query_text.strip()[:500]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO query_log(
                    id, workspace_id, query_text, confidence, latency_ms, source_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    workspace_id,
                    text,
                    normalized_confidence,
                    int(latency_ms),
                    int(source_count),
                    timestamp,
                ),
            )
            conn.commit()

    # // SPEC-014-008: Top queries default to last 30 days and support workspace filter.
    def top_queries(
        self,
        *,
        days: int = 30,
        workspace_id: str | None = None,
    ) -> list[QueryAggregate]:
        where_sql, params = self._window_filter(days=days, workspace_id=workspace_id)
        query = (
            "SELECT query_text, COUNT(*) AS frequency "
            "FROM query_log "
            f"{where_sql} "
            "GROUP BY query_text "
            "ORDER BY frequency DESC, query_text ASC "
            "LIMIT 20"
        )
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            QueryAggregate(query_text=str(row["query_text"]), frequency=int(row["frequency"]))
            for row in rows
        ]

    # // SPEC-014-008: P50/P95 are calculated in milliseconds from filtered rows.
    def latency_percentiles(
        self,
        *,
        days: int = 30,
        workspace_id: str | None = None,
    ) -> tuple[int | None, int | None]:
        where_sql, params = self._window_filter(days=days, workspace_id=workspace_id)
        query = f"SELECT latency_ms FROM query_log {where_sql} ORDER BY latency_ms ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        values = [int(row["latency_ms"]) for row in rows]
        if not values:
            return None, None
        return self._percentile(values, 0.50), self._percentile(values, 0.95)

    # // SPEC-014-008: Confidence distribution returns high/medium/low/refused percentages.
    def confidence_distribution(
        self,
        *,
        days: int = 30,
        workspace_id: str | None = None,
    ) -> list[ConfidenceBucket]:
        where_sql, params = self._window_filter(days=days, workspace_id=workspace_id)
        query = (
            "SELECT confidence, COUNT(*) AS count "
            "FROM query_log "
            f"{where_sql} "
            "GROUP BY confidence"
        )
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        counts = {label: 0 for label in VALID_CONFIDENCE}
        for row in rows:
            label = str(row["confidence"])
            if label in counts:
                counts[label] = int(row["count"])

        total = sum(counts.values())
        buckets: list[ConfidenceBucket] = []
        for label in VALID_CONFIDENCE:
            count = counts[label]
            percentage = (count / total * 100.0) if total else 0.0
            buckets.append(ConfidenceBucket(label=label, count=count, percentage=percentage))
        return buckets

    def workspace_ids(self, *, days: int = 30) -> list[str]:
        where_sql, params = self._window_filter(days=days, workspace_id=None)
        query = (
            "SELECT DISTINCT workspace_id FROM query_log "
            f"{where_sql} AND workspace_id IS NOT NULL "
            "ORDER BY workspace_id ASC"
        )
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [str(row["workspace_id"]) for row in rows]

    def _window_filter(self, *, days: int, workspace_id: str | None) -> tuple[str, tuple[str, ...]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        if workspace_id:
            return "WHERE created_at >= ? AND workspace_id = ?", (cutoff, workspace_id)
        return "WHERE created_at >= ?", (cutoff,)

    @staticmethod
    def _percentile(values: list[int], quantile: float) -> int:
        if len(values) == 1:
            return values[0]
        position = (len(values) - 1) * quantile
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        if lower == upper:
            return values[lower]
        lower_value = values[lower]
        upper_value = values[upper]
        interpolated = lower_value + (position - lower) * (upper_value - lower_value)
        return int(round(interpolated))

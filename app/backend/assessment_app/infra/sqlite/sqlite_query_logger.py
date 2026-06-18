"""SQLite adapter implementing QueryLogger and AnalyticsReader ports.

Handles both write (log_query) and read (analytics) on the same table.
Satisfies both assessment_app.services.query.internal.ports.QueryLogger
and assessment_app.services.analytics.internal.ports.AnalyticsReader.
"""

import sqlite3
from pathlib import Path

from assessment_app.services.query.public.models import QueryLogEntry


class SqliteQueryLogger:
    """SQLite-backed implementation of QueryLogger and AnalyticsReader.

    Creates the query_logs table on first connection.
    Thread-safety: creates a new connection per operation, which is safe
    for SQLite's default serialized mode.
    """

    def __init__(self, sqlite_path: Path) -> None:
        self._sqlite_path = sqlite_path
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── QueryLogger port ──────────────────────────────────────────────────────

    def log_query(self, entry: QueryLogEntry) -> None:
        """Insert one query log row."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO query_logs (query, answer, answer_found, latency_ms, sources_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (entry.query, entry.answer, int(entry.answer_found), entry.latency_ms, entry.sources_json),
            )

    # ── AnalyticsReader port ──────────────────────────────────────────────────

    def total_queries(self) -> int:
        row = self._fetch_one("SELECT COUNT(*) AS value FROM query_logs")
        return int(row["value"])

    def answer_found_rate(self) -> float:
        row = self._fetch_one("SELECT AVG(answer_found) AS value FROM query_logs")
        return float(row["value"] or 0)

    def average_latency_ms(self) -> float:
        row = self._fetch_one("SELECT AVG(latency_ms) AS value FROM query_logs")
        return float(row["value"] or 0)

    def frequent_questions(self, limit: int) -> list[dict]:
        return self._fetch_all(
            """
            SELECT query, COUNT(*) AS count
            FROM query_logs
            GROUP BY query
            ORDER BY count DESC, query ASC
            LIMIT ?
            """,
            (limit,),
        )

    def no_answer_queries(self, limit: int) -> list[dict]:
        return self._fetch_all(
            """
            SELECT query, created_at
            FROM query_logs
            WHERE answer_found = 0
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    answer_found INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    sources_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_one(self, query: str, params: tuple = ()) -> sqlite3.Row:
        with self._connect() as conn:
            return conn.execute(query, params).fetchone()

    def _fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

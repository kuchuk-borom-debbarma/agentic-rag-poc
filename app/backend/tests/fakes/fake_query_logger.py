"""Fake QueryLogger for unit tests.

Satisfies query.internal.ports.QueryLogger.
"""

from assessment_app.services.query.public.models import QueryLogEntry


class FakeQueryLogger:
    """Captures logged query entries in memory."""

    def __init__(self) -> None:
        self.logged: list[QueryLogEntry] = []

    def log_query(self, entry: QueryLogEntry) -> None:
        self.logged.append(entry)

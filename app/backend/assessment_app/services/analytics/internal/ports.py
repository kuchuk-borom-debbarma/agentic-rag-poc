"""Internal port definitions owned by the analytics service.

Infra adapters implement these protocols.
Other services must NOT import from this module.
"""

from typing import Protocol


class AnalyticsReader(Protocol):
    """Read-only port for aggregated query analytics."""

    def total_queries(self) -> int:
        """Return the total number of logged queries."""
        ...

    def answer_found_rate(self) -> float:
        """Return the fraction of queries where an answer was found."""
        ...

    def average_latency_ms(self) -> float:
        """Return the mean response latency in milliseconds."""
        ...

    def frequent_questions(self, limit: int) -> list[dict]:
        """Return the most-asked questions with counts."""
        ...

    def no_answer_queries(self, limit: int) -> list[dict]:
        """Return the most recent queries that returned no answer."""
        ...

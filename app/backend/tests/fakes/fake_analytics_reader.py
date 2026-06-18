"""Fake AnalyticsReader for unit tests.

Satisfies analytics.internal.ports.AnalyticsReader.
"""


class FakeAnalyticsReader:
    """Returns configurable canned analytics values."""

    def __init__(
        self,
        total: int = 0,
        found_rate: float = 0.0,
        avg_latency: float = 0.0,
        frequent: list | None = None,
        no_answer: list | None = None,
    ) -> None:
        self._total = total
        self._found_rate = found_rate
        self._avg_latency = avg_latency
        self._frequent = frequent or []
        self._no_answer = no_answer or []

    def total_queries(self) -> int:
        return self._total

    def answer_found_rate(self) -> float:
        return self._found_rate

    def average_latency_ms(self) -> float:
        return self._avg_latency

    def frequent_questions(self, limit: int) -> list[dict]:
        return self._frequent[:limit]

    def no_answer_queries(self, limit: int) -> list[dict]:
        return self._no_answer[:limit]

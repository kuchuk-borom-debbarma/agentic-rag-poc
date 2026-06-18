"""Default implementation of the AnalyticsService.

Delegates all reads to the AnalyticsReader port.
Does not know whether the reader is SQLite, Postgres, or in-memory.
"""

from assessment_app.services.analytics.internal.ports import AnalyticsReader
from assessment_app.services.analytics.public.contracts import AnalyticsService
from assessment_app.services.analytics.public.models import AnalyticsSummary


class DefaultAnalyticsService:
    """Reads aggregated analytics via the AnalyticsReader port."""

    def __init__(self, analytics_reader: AnalyticsReader) -> None:
        self._analytics_reader = analytics_reader

    def summary(self) -> AnalyticsSummary:
        """Return aggregated analytics across all logged queries."""
        return AnalyticsSummary(
            total_queries=self._analytics_reader.total_queries(),
            answer_found_rate=self._analytics_reader.answer_found_rate(),
            average_latency_ms=self._analytics_reader.average_latency_ms(),
            frequent_questions=self._analytics_reader.frequent_questions(limit=10),
            no_answer_queries=self._analytics_reader.no_answer_queries(limit=10),
        )


# Runtime type check: DefaultAnalyticsService must satisfy AnalyticsService.
_: AnalyticsService = DefaultAnalyticsService.__new__(DefaultAnalyticsService)  # type: ignore[assignment]

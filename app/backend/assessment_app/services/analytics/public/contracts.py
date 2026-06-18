"""Public contract for the analytics bounded context.

Only this file (and models.py / errors.py) may be imported by routes, other services, or config.
"""

from typing import Protocol

from assessment_app.services.analytics.public.models import AnalyticsSummary


class AnalyticsService(Protocol):
    """Public contract for reading query analytics."""

    def summary(self) -> AnalyticsSummary:
        """Return aggregated analytics across all logged queries."""
        ...

"""Public models for the analytics bounded context."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AnalyticsSummary:
    """Aggregated query analytics summary."""

    total_queries: int
    answer_found_rate: float
    average_latency_ms: float
    frequent_questions: list[dict] = field(default_factory=list)
    no_answer_queries: list[dict] = field(default_factory=list)

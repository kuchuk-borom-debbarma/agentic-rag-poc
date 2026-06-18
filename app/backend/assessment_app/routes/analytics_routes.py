"""Analytics route.

Depends on the AnalyticsService contract only.
No try/except — global exception handlers map domain errors to HTTP.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from assessment_app.config.dependencies import AnalyticsServiceDep

router = APIRouter()


class AnalyticsResponse(BaseModel):
    total_queries: int
    answer_found_rate: float
    average_latency_ms: float
    frequent_questions: list[dict]
    no_answer_queries: list[dict]


@router.get("", response_model=AnalyticsResponse)
async def analytics(service: AnalyticsServiceDep) -> AnalyticsResponse:
    """Return aggregated analytics across all logged queries."""
    summary = service.summary()
    return AnalyticsResponse(
        total_queries=summary.total_queries,
        answer_found_rate=summary.answer_found_rate,
        average_latency_ms=summary.average_latency_ms,
        frequent_questions=summary.frequent_questions,
        no_answer_queries=summary.no_answer_queries,
    )

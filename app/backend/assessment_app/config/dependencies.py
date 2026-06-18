"""FastAPI dependency providers.

Thin functions that retrieve already-wired service instances from app.state.container.
No business logic. No dependency construction.
"""

from typing import Annotated

from fastapi import Depends, Request

from assessment_app.config.container import AppContainer
from assessment_app.services.analytics.public.contracts import AnalyticsService
from assessment_app.services.evaluation.public.contracts import EvaluationService
from assessment_app.services.query.public.contracts import QueryService
from assessment_app.services.rag.public.contracts import RagIngestionService


def _get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_query_service(request: Request) -> QueryService:
    return _get_container(request).query_service


def get_analytics_service(request: Request) -> AnalyticsService:
    return _get_container(request).analytics_service


def get_evaluation_service(request: Request) -> EvaluationService:
    return _get_container(request).evaluation_service


def get_rag_ingestion_service(request: Request) -> RagIngestionService:
    return _get_container(request).rag_ingestion_service


# Convenience Annotated types for route function signatures.
QueryServiceDep = Annotated[QueryService, Depends(get_query_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]
EvaluationServiceDep = Annotated[EvaluationService, Depends(get_evaluation_service)]
RagIngestionServiceDep = Annotated[RagIngestionService, Depends(get_rag_ingestion_service)]

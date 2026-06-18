"""Global exception handlers.

Maps service-level domain errors to HTTP responses.
Services never raise HTTPException — this is the only layer that does.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from assessment_app.services.evaluation.public.errors import (
    BenchmarkCaseNotFoundError,
    EvaluationError,
    EvaluationRunNotFoundError,
)
from assessment_app.services.query.public.errors import NotIngestedError, QueryError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain-error-to-HTTP mappings on the app."""

    @app.exception_handler(NotIngestedError)
    async def handle_not_ingested(request: Request, exc: NotIngestedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "NOT_INGESTED", "message": str(exc)},
        )

    @app.exception_handler(QueryError)
    async def handle_query_error(request: Request, exc: QueryError) -> JSONResponse:
        logger.warning("Query service error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "QUERY_ERROR", "message": str(exc)},
        )

    @app.exception_handler(EvaluationRunNotFoundError)
    async def handle_evaluation_run_not_found(request: Request, exc: EvaluationRunNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "EVALUATION_RUN_NOT_FOUND", "message": str(exc)},
        )

    @app.exception_handler(BenchmarkCaseNotFoundError)
    async def handle_benchmark_case_not_found(request: Request, exc: BenchmarkCaseNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "BENCHMARK_CASE_NOT_FOUND", "message": str(exc)},
        )

    @app.exception_handler(EvaluationError)
    async def handle_evaluation_error(request: Request, exc: EvaluationError) -> JSONResponse:
        logger.warning("Evaluation service error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "EVALUATION_ERROR", "message": str(exc)},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected server error")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
            },
        )

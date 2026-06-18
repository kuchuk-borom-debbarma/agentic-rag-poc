"""Ask (RAG query) route.

Depends on the QueryService contract only.
No try/except — global exception handlers map domain errors to HTTP.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from assessment_app.config.dependencies import QueryServiceDep
from assessment_app.routes.dtos import SourceResponse

router = APIRouter()


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class AskResponse(BaseModel):
    answer: str
    answer_found: bool
    latency_ms: int
    sources: list[SourceResponse]


@router.post("", response_model=AskResponse)
async def ask(request: AskRequest, service: QueryServiceDep) -> AskResponse:
    """Answer a question against the ingested document using RAG."""
    result = service.ask(request.query.strip(), request.top_k)
    return AskResponse(
        answer=result.answer,
        answer_found=result.answer_found,
        latency_ms=result.latency_ms,
        sources=[SourceResponse(**source.__dict__) for source in result.sources],
    )

"""Ask (RAG query) route.

Depends on the QueryService contract only.
No try/except — global exception handlers map domain errors to HTTP.
"""

import json
from dataclasses import asdict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from assessment_app.config.dependencies import QueryServiceDep
from assessment_app.routes.dtos import QueryTraceResponse, SourceResponse

router = APIRouter()


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    max_loops: int | None = Field(default=4, ge=1, le=10)


class AskResponse(BaseModel):
    answer: str
    answer_found: bool
    latency_ms: int
    sources: list[SourceResponse]
    trace: QueryTraceResponse | None = None


@router.post("")
async def ask(request: AskRequest, service: QueryServiceDep) -> StreamingResponse:
    """Answer a question against the ingested document using RAG."""
    def event_generator():
        for event in service.ask(request.query.strip(), top_k=request.top_k, max_loops=request.max_loops):
            if event.get("type") == "complete":
                result = event["result"]
                response = AskResponse(
                    answer=result.answer,
                    answer_found=result.answer_found,
                    latency_ms=result.latency_ms,
                    sources=[SourceResponse(**source.__dict__) for source in result.sources],
                    trace=QueryTraceResponse(**asdict(result.trace)) if result.trace else None,
                )
                yield f"data: {json.dumps({'type': 'complete', 'result': response.model_dump()})}\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")

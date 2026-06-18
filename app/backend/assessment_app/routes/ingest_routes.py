"""RAG ingestion rebuild route."""

from fastapi import APIRouter
from pydantic import BaseModel

from assessment_app.config.dependencies import RagIngestionServiceDep

router = APIRouter()


class IngestResponse(BaseModel):
    """HTTP response for an ingestion rebuild."""

    section_count: int
    chunk_count: int
    graph_chunk_count: int
    vector_count: int


@router.post("", response_model=IngestResponse)
async def rebuild_ingestion(service: RagIngestionServiceDep) -> IngestResponse:
    """Rebuild configured PDF ingestion data."""
    result = service.rebuild()
    return IngestResponse(**result.__dict__)

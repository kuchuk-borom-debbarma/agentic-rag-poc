"""API tests for the RAG ingest route."""

from fastapi.testclient import TestClient

from assessment_app.config.dependencies import get_rag_ingestion_service
from assessment_app.main import create_app
from assessment_app.services.rag.public.models import RagIngestionResult


def test_ingest_route_returns_rebuild_counts():
    app = create_app()
    app.dependency_overrides[get_rag_ingestion_service] = lambda: _FakeRagIngestionService()

    with TestClient(app) as client:
        response = client.post("/api/v1/ingest")

    assert response.status_code == 200
    assert response.json() == {
        "section_count": 2,
        "chunk_count": 3,
        "graph_chunk_count": 3,
        "vector_count": 3,
    }


class _FakeRagIngestionService:
    def rebuild(self) -> RagIngestionResult:
        return RagIngestionResult(
            section_count=2,
            chunk_count=3,
            graph_chunk_count=3,
            vector_count=3,
        )

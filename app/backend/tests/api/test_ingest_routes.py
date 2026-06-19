"""API tests for the RAG ingest route."""

from fastapi.testclient import TestClient

from assessment_app.config.dependencies import get_rag_ingestion_service
from assessment_app.main import create_app
from assessment_app.services.rag.public.models import GraphEdge, GraphNode, GraphVisualization, RagIngestionResult


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


def test_ingest_graph_route_returns_visualization_data():
    app = create_app()
    app.dependency_overrides[get_rag_ingestion_service] = lambda: _FakeRagIngestionService()

    with TestClient(app) as client:
        response = client.get("/api/v1/ingest/graph")

    assert response.status_code == 200
    assert response.json() == {
        "sections_count": 1,
        "chunks_count": 1,
        "references_count": 1,
        "total_nodes": 2,
        "total_edges": 2,
        "offset": 0,
        "limit": 120,
        "nodes": [
            {
                "id": "section_1",
                "label": "1 Definitions",
                "kind": "section",
                "parent_id": None,
                "section_id": "section_1",
                "text_preview": None,
            },
            {
                "id": "section_1_chunk_0",
                "label": "section_1_chunk_0",
                "kind": "chunk",
                "parent_id": "section_1",
                "section_id": "section_1",
                "text_preview": "Definitions content.",
            },
        ],
        "edges": [
            {"source": "section_1", "target": "section_1_chunk_0", "kind": "contains"},
            {"source": "section_1_chunk_0", "target": "section_2", "kind": "references"},
        ],
    }


class _FakeRagIngestionService:
    def rebuild(self) -> RagIngestionResult:
        return RagIngestionResult(
            section_count=2,
            chunk_count=3,
            graph_chunk_count=3,
            vector_count=3,
        )

    def get_graph_visualization(self, offset: int = 0, limit: int = 120) -> GraphVisualization:
        return GraphVisualization(
            sections_count=1,
            chunks_count=1,
            references_count=1,
            total_nodes=2,
            total_edges=2,
            offset=offset,
            limit=limit,
            nodes=[
                GraphNode("section_1", "1 Definitions", "section", None, "section_1", None),
                GraphNode(
                    "section_1_chunk_0",
                    "section_1_chunk_0",
                    "chunk",
                    "section_1",
                    "section_1",
                    "Definitions content.",
                ),
            ],
            edges=[
                GraphEdge("section_1", "section_1_chunk_0", "contains"),
                GraphEdge("section_1_chunk_0", "section_2", "references"),
            ],
        )

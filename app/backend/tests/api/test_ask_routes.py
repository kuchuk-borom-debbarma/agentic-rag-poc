"""API tests for ask route trace payloads."""

from fastapi.testclient import TestClient

from assessment_app.config.dependencies import get_query_service
from assessment_app.main import create_app
from assessment_app.services.query.public.models import (
    AskResult,
    QueryTrace,
    RetrievalStepTrace,
    SourceSnippet,
    TraceCandidate,
)


def test_ask_route_returns_answer_with_optional_trace():
    app = create_app()
    app.dependency_overrides[get_query_service] = lambda: _FakeQueryService()

    with TestClient(app) as client:
        response = client.post("/api/v1/ask", json={"query": "What does Section 6.1 say?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "AWS obtains no rights to Your Content [S1]."
    assert payload["sources"][0]["section_number"] == "6.1"
    assert payload["trace"]["retrieval_steps"][0]["validated_sections"] == ["6.1"]
    assert payload["trace"]["final_sources"][0]["chunk_id"] == "section_6_1:0:0"


class _FakeQueryService:
    def ask(self, query: str, top_k: int | None = None, log_query: bool = True) -> AskResult:
        source = _source()
        candidate = TraceCandidate(
            chunk_id=source.chunk_id,
            section_number=source.section_number,
            section_title=source.section_title,
            source_type="exact_section",
            score=99.0,
            text_preview="Except as provided in this Section 6, AWS obtains no rights.",
        )
        return AskResult(
            answer="AWS obtains no rights to Your Content [S1].",
            answer_found=True,
            sources=[source],
            latency_ms=10,
            trace=QueryTrace(
                original_query=query,
                retrieval_steps=[
                    RetrievalStepTrace(
                        query_id="Q1",
                        query=query,
                        expanded_query=query,
                        explicit_sections=["6.1"],
                        validated_sections=["6.1"],
                        vector_candidates=[],
                        lexical_candidates=[candidate],
                        reranked_candidates=[candidate],
                    )
                ],
                final_sources=[candidate],
            ),
        )


def _source() -> SourceSnippet:
    return SourceSnippet(
        chunk_id="section_6_1:0:0",
        text="Except as provided in this Section 6, we obtain no rights under this Agreement from you.",
        page_start=1,
        page_end=1,
        source_file="doc.pdf",
        section_id="section_6_1",
        section_number="6.1",
        section_title="Your Content",
        parent_section_id="section_6",
        parent_section_number="6",
        parent_section_title="Proprietary Rights",
        order=60100000,
        referenced_section_ids=[],
        source_type="exact_section",
        score=99.0,
    )

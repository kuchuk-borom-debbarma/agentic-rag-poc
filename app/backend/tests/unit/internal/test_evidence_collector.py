"""Unit tests for EvidenceCollector."""

from assessment_app.services.query.public.models import QueryPlan, RetrievalQuery, SourceSnippet, VerificationResult
from assessment_app.services.query.internal.evidence_collector import EvidenceCollector
from tests.fakes.fake_embedding_client import FakeEmbeddingClient
from tests.fakes.fake_vector_store import FakeSemanticStore


class _ExpandingGraphStore:
    def get_chunk(self, chunk_id: str):
        return _snippet(chunk_id, 1, "2.1", "semantic")

    def get_section_chunks(self, section_numbers):
        return [_snippet("chunk_0002", 2, "2.1", "exact_section")] if section_numbers else []

    def get_neighbors(self, chunk_ids, neighbors):
        return [_snippet("chunk_0000", 0, "2", "neighbor")]

    def get_referenced_sections(self, chunk_ids, limit=2):
        return [_snippet("chunk_0003", 3, "1.1", "reference")]

    def get_parent_sections(self, chunk_ids):
        return [_snippet("chunk_0004", -1, "2", "parent")]

    def get_child_sections(self, chunk_ids):
        return []


def test_evidence_collector_expands_and_dedupes():
    query = RetrievalQuery("Q1", "q", "original", ["2.1"], True)

    semantic_store = FakeSemanticStore(
        snippets=[_snippet("chunk_0001", 1, "2.1", "semantic")],
        chunk_count=3
    )

    collector = EvidenceCollector(
        embedding_client=FakeEmbeddingClient(),
        semantic_store=semantic_store,
        graph_store=_ExpandingGraphStore(),
        top_k=5,
    )
    
    initial = collector.initial_search(query)
    assert [item.chunk_id for item in initial] == ["chunk_0001", "chunk_0002"]
    
    verification = VerificationResult(
        is_sufficient=False,
        needs_references=True,
        needs_neighbors=True,
        needs_parents=True,
        needs_children=False,
        issues=[]
    )
    
    expanded = collector.expand_context(initial, verification)

    assert [item.chunk_id for item in expanded] == ["chunk_0004", "chunk_0000", "chunk_0001", "chunk_0002", "chunk_0003"]


def _snippet(chunk_id, order, section_number, source_type) -> SourceSnippet:
    return SourceSnippet(
        chunk_id=chunk_id,
        text=f"text {chunk_id}",
        page_start=1,
        page_end=1,
        source_file="doc.pdf",
        section_id=f"section_{section_number.replace('.', '_')}",
        section_number=section_number,
        section_title="Title",
        parent_section_id=None,
        parent_section_number=None,
        parent_section_title=None,
        order=order,
        referenced_section_ids=[],
        source_type=source_type,
        score=None,
    )

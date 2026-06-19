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

    def search_lexical(self, query, limit=20):
        return []


def test_evidence_collector_expands_and_dedupes():
    query = RetrievalQuery("Q1", "According to Section 2.1, q", "original", ["2.1"], True)

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


def test_evidence_collector_hybrid_reranks_security_clause():
    collector = _collector_for_hybrid_tests()

    result = collector.initial_search(
        RetrievalQuery("Q1", "What does AWS promise about securing customer content?", "test", [], False),
        top_k=3,
    )

    assert collector.last_trace_step.reranked_candidates[0].section_number == "1.3"
    assert any(item.section_number == "1.3" for item in result)


def test_evidence_collector_hybrid_reranks_ownership_clause():
    collector = _collector_for_hybrid_tests()

    result = collector.initial_search(
        RetrievalQuery("Q1", "Does AWS obtain ownership rights in customer content?", "test", [], False),
        top_k=3,
    )

    assert collector.last_trace_step.reranked_candidates[0].section_number == "6.1"
    assert any(item.section_number == "6.1" for item in result)


def test_evidence_collector_hybrid_reranks_term_clause():
    collector = _collector_for_hybrid_tests()

    result = collector.initial_search(
        RetrievalQuery("Q1", "When does the AWS Customer Agreement term start and end?", "test", [], False),
        top_k=3,
    )

    assert collector.last_trace_step.reranked_candidates[0].section_number == "5.1"
    assert any(item.section_number == "5.1" for item in result)


def test_evidence_collector_exact_section_fetches_explicit_section():
    collector = _collector_for_hybrid_tests()

    result = collector.initial_search(
        RetrievalQuery("Q1", "What does Section 6.1 say?", "test", [], False),
        top_k=3,
    )

    assert collector.last_trace_step.reranked_candidates[0].section_number == "6.1"
    assert any(item.section_number == "6.1" and item.source_type == "exact_section" for item in result)


def test_evidence_collector_ignores_unvalidated_planned_target():
    collector = _collector_for_hybrid_tests()

    result = collector.initial_search(
        RetrievalQuery("Q1", "Does AWS obtain ownership rights in customer content?", "test", ["1.1"], False),
        top_k=3,
    )

    assert all(item.section_number != "1.1" or item.source_type != "exact_section" for item in result)


def _collector_for_hybrid_tests():
    snippets = [
        _rich_snippet(
            "section_8:0:0",
            "8",
            "Disclaimers",
            "THE SERVICES AND AWS CONTENT ARE PROVIDED AS IS. AWS disclaims warranties that any Content will be secure or not otherwise lost or altered.",
            80000000,
            "semantic",
        ),
        _rich_snippet(
            "section_1_3:0:0",
            "1.3",
            "AWS Security",
            "Without limiting Section 8 or your obligations under Section 2.2, we will implement reasonable and appropriate measures designed to help you secure Your Content against accidental or unlawful loss, access or disclosure.",
            10300000,
            "lexical",
        ),
        _rich_snippet(
            "section_6_1:0:0",
            "6.1",
            "Your Content",
            "Except as provided in this Section 6, we obtain no rights under this Agreement from you or your licensors to Your Content. You consent to our use of Your Content to provide the Services.",
            60100000,
            "lexical",
        ),
        _rich_snippet(
            "section_5_1:0:0",
            "5.1",
            "Term",
            "The term of this Agreement will commence on the Effective Date and will remain in effect until terminated under this Section 5.",
            50100000,
            "lexical",
        ),
        _rich_snippet(
            "section_front_matter:0:0",
            "front.matter",
            "Front Matter",
            "AWS Customer Agreement",
            0,
            "semantic",
        ),
        _rich_snippet(
            "section_1_1:0:0",
            "1.1",
            "General",
            "You may access and use the Services in accordance with this Agreement.",
            10100000,
            "semantic",
        ),
    ]
    graph_store = _HybridGraphStore(snippets)
    semantic_store = FakeSemanticStore(
        snippets=[snippets[0], snippets[4]],
        chunk_count=len(snippets),
    )
    return EvidenceCollector(
        embedding_client=FakeEmbeddingClient(),
        semantic_store=semantic_store,
        graph_store=graph_store,
        top_k=5,
    )


class _HybridGraphStore:
    def __init__(self, snippets):
        self._snippets = {snippet.chunk_id: snippet for snippet in snippets}
        self._by_section = {snippet.section_number: snippet for snippet in snippets}

    def get_chunk(self, chunk_id):
        return self._snippets.get(chunk_id)

    def get_section_chunks(self, section_numbers):
        return [self._by_section[number] for number in section_numbers if number in self._by_section]

    def search_lexical(self, query, limit=20):
        lower = query.lower()
        result = []
        for snippet in self._snippets.values():
            haystack = f"{snippet.section_title} {snippet.text}".lower()
            if any(token in haystack for token in lower.split()):
                result.append(snippet)
        return result[:limit]

    def get_neighbors(self, chunk_ids, neighbors=1):
        return []

    def get_referenced_sections(self, chunk_ids, limit=2):
        return []

    def get_parent_sections(self, chunk_ids):
        return []

    def get_child_sections(self, chunk_ids):
        return []


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


def _rich_snippet(chunk_id, section_number, title, text, order, source_type) -> SourceSnippet:
    return SourceSnippet(
        chunk_id=chunk_id,
        text=text,
        page_start=1,
        page_end=1,
        source_file="doc.pdf",
        section_id=f"section_{section_number.replace('.', '_')}",
        section_number=section_number,
        section_title=title,
        parent_section_id=None,
        parent_section_number=None,
        parent_section_title=None,
        order=order,
        referenced_section_ids=[],
        source_type=source_type,
        score=None,
    )

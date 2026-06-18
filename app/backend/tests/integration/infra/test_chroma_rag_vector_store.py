"""Integration tests for Stage 4 Chroma RAG vector storage."""

from assessment_app.infra.chroma.chroma_rag_vector_store import ChromaRagVectorStore
from assessment_app.services.rag.internal.ingestion.graph_builder import GraphBuilder
from assessment_app.services.rag.internal.ingestion.models import ChunkedContent, Reference, Section


def test_chroma_rag_vector_store_replaces_chunks_and_searches_by_cosine(tmp_path):
    from unittest.mock import MagicMock
    mock_embeddings = MagicMock()
    store = ChromaRagVectorStore(tmp_path / "chroma", "rag_chunks", embedding_function=mock_embeddings)
    sections = [
        Section(id="section_1", title="Terms", parent=None, layout=[]),
        Section(id="section_2", title="Fees", parent="section_1", layout=[]),
    ]
    chunks = [
        ChunkedContent("section_1", 0, 0, "Terms mention Fees.", [Reference("section_2", 14, 18)], [1.0, 0.0]),
        ChunkedContent("section_2", 0, 0, "Fees content.", [], [0.0, 1.0]),
    ]
    graph = GraphBuilder().build(sections, chunks)

    store.replace_chunks(chunks, graph)

    assert store.count() == 2
    match = store.search_by_embedding([1.0, 0.0], top_k=1)[0]
    assert match.chunk_id == "section_1:0:0"
    assert match.section_id == "section_1"
    assert match.parent_section_id is None
    assert match.layout_index == 0
    assert match.chunk_index == 0
    assert match.referenced_section_ids == ["section_2"]

    fresh_chunks = [ChunkedContent("section_2", 0, 0, "Only fresh.", [], [0.0, 1.0])]
    fresh_graph = GraphBuilder().build(sections, fresh_chunks)
    store.replace_chunks(fresh_chunks, fresh_graph)

    assert store.count() == 1
    assert store.search_by_embedding([1.0, 0.0], top_k=1)[0].chunk_id == "section_2:0:0"

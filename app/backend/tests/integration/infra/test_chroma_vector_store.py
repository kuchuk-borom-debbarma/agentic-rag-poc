"""Integration tests for ChromaVectorStore."""

from assessment_app.infra.chroma.chroma_vector_store import ChromaVectorStore
from assessment_app.services.rag.public.models import DocumentChunk


def test_chroma_vector_store_supports_graph_evidence_methods(tmp_path):
    store = ChromaVectorStore(tmp_path / "chroma", "test_chunks")
    chunks = [
        _chunk("chunk_0000", "1. Terms. See Section 2.1.", "1", "Terms", 0, references=["section_2_1"]),
        _chunk("chunk_0001", "2. Billing.", "2", "Billing", 1),
        _chunk("chunk_0002", "2.1 Fees. You pay all fees.", "2.1", "Fees", 2, parent_number="2"),
    ]
    store.add_chunks(chunks, [[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]])

    assert store.count() == 3
    assert store.search([1.0, 0.0], top_k=1)[0].section_number == "1"
    neighbor_ids = [row.chunk_id for row in store.get_neighbors([1], before=1, after=1)]
    assert neighbor_ids == ["chunk_0000", "chunk_0001", "chunk_0002"]
    assert store.get_section_chunks(["2.1"])[0].section_title == "Fees"
    assert store.get_referenced_sections(["chunk_0000"])[0].section_number == "2.1"


def _chunk(
    chunk_id: str,
    text: str,
    section_number: str,
    section_title: str,
    order: int,
    parent_number: str | None = None,
    references: list[str] | None = None,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        text=text,
        page_start=1,
        page_end=1,
        source_file="doc.pdf",
        section_id=f"section_{section_number.replace('.', '_')}",
        section_number=section_number,
        section_title=section_title,
        parent_section_id=f"section_{parent_number}" if parent_number else None,
        parent_section_number=parent_number,
        parent_section_title="Billing" if parent_number else None,
        order=order,
        previous_chunk_id=None,
        next_chunk_id=None,
        referenced_section_ids=references or [],
    )

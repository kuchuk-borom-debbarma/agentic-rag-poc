"""Public models for the RAG bounded context."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentBlock:
    text: str
    box_class: str
    page_start: int
    page_end: int


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    source_file: str
    section_id: str
    section_number: str
    section_title: str
    parent_section_id: str | None
    parent_section_number: str | None
    parent_section_title: str | None
    order: int
    previous_chunk_id: str | None
    next_chunk_id: str | None
    referenced_section_ids: list[str]


@dataclass(frozen=True)
class RagIngestionResult:
    """Summary returned after rebuilding RAG ingestion data."""

    section_count: int
    chunk_count: int
    graph_chunk_count: int
    vector_count: int

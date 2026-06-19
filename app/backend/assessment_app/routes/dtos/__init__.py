"""Shared HTTP response DTOs used by multiple route modules."""

from pydantic import BaseModel


class SourceResponse(BaseModel):
    """HTTP response shape for a single retrieved source snippet."""

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
    referenced_section_ids: list[str]
    source_type: str
    score: float | None = None


class TraceCandidateResponse(BaseModel):
    chunk_id: str
    section_number: str
    section_title: str
    source_type: str
    score: float | None
    text_preview: str


class VerificationTraceResponse(BaseModel):
    is_sufficient: bool
    needs_references: bool
    needs_parents: bool
    needs_children: bool
    needs_neighbors: bool
    issues: list[str]


class RetrievalStepTraceResponse(BaseModel):
    query_id: str
    query: str
    expanded_query: str
    explicit_sections: list[str]
    validated_sections: list[str]
    vector_candidates: list[TraceCandidateResponse]
    lexical_candidates: list[TraceCandidateResponse]
    reranked_candidates: list[TraceCandidateResponse]
    verifier: VerificationTraceResponse | None = None
    expansion_actions: list[str] | None = None


class QueryTraceResponse(BaseModel):
    original_query: str
    retrieval_steps: list[RetrievalStepTraceResponse]
    final_sources: list[TraceCandidateResponse]

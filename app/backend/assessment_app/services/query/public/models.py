"""Public models for the query bounded context."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSnippet:
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

    @property
    def section_label(self) -> str:
        if self.section_number == "front_matter":
            return "Front Matter"
        return f"Section {self.section_number} - {self.section_title}".strip(" -")


@dataclass(frozen=True)
class RetrievalQuery:
    query_id: str
    query: str
    purpose: str
    target_sections: list[str]
    include_references: bool


@dataclass(frozen=True)
class QueryPlan:
    original_query: str
    retrieval_queries: list[RetrievalQuery]


@dataclass(frozen=True)
class VerificationResult:
    is_sufficient: bool
    needs_references: bool
    needs_parents: bool
    needs_children: bool
    needs_neighbors: bool
    issues: list[str]


@dataclass(frozen=True)
class TraceCandidate:
    """Bounded retrieval candidate detail for UI/debug traces."""

    chunk_id: str
    section_number: str
    section_title: str
    source_type: str
    score: float | None
    text_preview: str


@dataclass(frozen=True)
class RetrievalStepTrace:
    """Trace for one planned retrieval query."""

    query_id: str
    query: str
    expanded_query: str
    explicit_sections: list[str]
    validated_sections: list[str]
    vector_candidates: list[TraceCandidate]
    lexical_candidates: list[TraceCandidate]
    reranked_candidates: list[TraceCandidate]
    verifier: VerificationResult | None = None
    expansion_actions: list[str] | None = None


@dataclass(frozen=True)
class QueryTrace:
    """Bounded trace for the query pipeline."""

    original_query: str
    retrieval_steps: list[RetrievalStepTrace]
    final_sources: list[TraceCandidate]


@dataclass(frozen=True)
class QueryLogEntry:
    query: str
    answer: str
    answer_found: bool
    latency_ms: int
    sources_json: str


@dataclass(frozen=True)
class AskResult:
    """Result of a single RAG query."""

    answer: str
    answer_found: bool
    sources: list[SourceSnippet]
    latency_ms: int
    trace: QueryTrace | None = None

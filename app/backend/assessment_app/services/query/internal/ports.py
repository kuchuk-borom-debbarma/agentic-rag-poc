"""Internal port definitions owned by the query service.

Infra adapters implement these protocols.
Other services must NOT import from this module.
"""

from typing import Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings

from assessment_app.services.rag.public.models import DocumentChunk
from assessment_app.services.query.public.models import SourceSnippet
from assessment_app.services.query.public.models import QueryLogEntry, VerificationResult


class SemanticStore(Protocol):
    """Semantic vector store port. Only returns matching chunk IDs and scores."""

    def search(self, query_embedding: list[float], top_k: int) -> list[tuple[str, float]]:
        """Search for chunks by semantic similarity. Returns list of (chunk_id, score)."""
        ...

    def count(self) -> int:
        """Return the total number of stored chunks."""
        ...


class GraphStore(Protocol):
    """Graph store port for fetching exact chunks, neighbors, and references."""

    def get_chunk(self, chunk_id: str) -> SourceSnippet | None:
        """Fetch a specific chunk by ID."""
        ...

    def get_neighbors(self, chunk_ids: list[str], neighbors: int = 1) -> list[SourceSnippet]:
        """Fetch chunks immediately surrounding the given chunks."""
        ...

    def get_section_chunks(self, section_numbers: list[str]) -> list[SourceSnippet]:
        """Fetch all chunks belonging to specified section numbers."""
        ...

    def get_referenced_sections(self, chunk_ids: list[str], limit: int = 2) -> list[SourceSnippet]:
        """Fetch the first N chunks from sections referenced by the given chunks."""
        ...

    def get_parent_sections(self, chunk_ids: list[str]) -> list[SourceSnippet]:
        """Fetch chunks from the parent sections of the given chunks."""
        ...

    def get_child_sections(self, chunk_ids: list[str]) -> list[SourceSnippet]:
        """Fetch chunks from the child sections of the given chunks."""
        ...


class EvidenceVerifier(Protocol):
    """Self-reflective RAG verifier."""

    def verify(self, query: str, evidence: list[SourceSnippet]) -> VerificationResult:
        """Verify if the evidence is sufficient to answer the query."""
        ...





class QueryLogger(Protocol):
    """Persist query log entries for analytics."""

    def log_query(self, entry: QueryLogEntry) -> None:
        """Write one query log entry to durable storage."""
        ...

"""Public service contract for the RAG bounded context."""

from typing import Protocol

from assessment_app.services.rag.public.models import RagIngestionResult


class RagIngestionService(Protocol):
    """Public contract for rebuilding RAG ingestion data."""

    def rebuild(self) -> RagIngestionResult:
        """Rebuild parsed sections, graph maps, and vector records."""
        ...

"""Internal ports owned by the RAG ingestion stage."""

from typing import Protocol

from assessment_app.services.rag.public.models import DocumentBlock
from assessment_app.services.rag.internal.ingestion.models import ChunkedContent, GraphMaps, VectorMatch


class DocumentLoader(Protocol):
    """Load source document pages from a file system or storage."""

    def load(self) -> list[DocumentBlock]:
        """Return extracted source layout blocks."""
        ...


from langchain_core.embeddings import Embeddings


class GraphStore(Protocol):
    """Persist and load lightweight graph maps."""

    def replace_graph(self, graph: GraphMaps) -> None:
        """Atomically replace all stored graph maps."""
        ...

    def load_graph(self) -> GraphMaps:
        """Load graph maps from storage."""
        ...


class RagVectorStore(Protocol):
    """Persist semantic chunks and search their cached embeddings."""

    def replace_chunks(self, chunks: list[ChunkedContent], graph: GraphMaps) -> None:
        """Atomically replace vector records for chunked content."""
        ...

    def search_by_embedding(self, embedding: list[float], top_k: int) -> list[VectorMatch]:
        """Return nearest chunk matches for a precomputed query embedding."""
        ...

    def count(self) -> int:
        """Return total stored vector chunk count."""
        ...

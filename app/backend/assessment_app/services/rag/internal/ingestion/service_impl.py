"""Default implementation of the hierarchical parsing ingestion stage."""

from dataclasses import replace

from assessment_app.services.rag.internal.ingestion.models import ChunkedContent, Section
from assessment_app.services.rag.internal.ingestion.parser import HierarchicalAwareParser
from assessment_app.services.rag.internal.ingestion.ports import DocumentLoader, Embeddings
from assessment_app.services.rag.internal.ingestion.semantic_chunker import SemanticChunker
from assessment_app.services.rag.internal.ingestion.validator import StructureValidator


class DefaultIngestionParsingService:
    """Load source pages and parse them into hierarchical sections."""

    def __init__(
        self,
        document_loader: DocumentLoader,
        parser: HierarchicalAwareParser,
        validator: StructureValidator | None = None,
    ) -> None:
        self._document_loader = document_loader
        self._parser = parser
        self._validator = validator or StructureValidator()

    def parse(self) -> list[Section]:
        """Return parsed sections from the source document."""
        sections = self._parser.parse(self._document_loader.load())
        self._validator.validate(sections)
        return sections


class DefaultSemanticChunkingService:
    """Chunk parsed sections and attach cached embeddings."""

    def __init__(self, chunker: SemanticChunker, embedding_client: Embeddings) -> None:
        self._chunker = chunker
        self._embedding_client = embedding_client

    def chunk(self, sections: list[Section]) -> list[ChunkedContent]:
        """Return semantic chunks with embeddings calculated once."""
        chunks = self._chunker.chunk(sections)
        if not chunks:
            return []

        texts = [chunk.text for chunk in chunks]
        batch_size = 50
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            embeddings.extend(self._embedding_client.embed_documents(batch_texts))
        return [
            replace(chunk, embedding=embedding)
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]

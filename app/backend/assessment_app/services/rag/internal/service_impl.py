"""Default RAG bounded-context service implementations."""

import logging
import threading
from assessment_app.services.rag.internal.ingestion.graph_builder import GraphBuilder
from assessment_app.services.rag.internal.ingestion.ports import GraphStore, RagVectorStore
from assessment_app.services.rag.internal.ingestion.service_impl import (
    DefaultIngestionParsingService,
    DefaultSemanticChunkingService,
)
from assessment_app.services.rag.public.contracts import RagIngestionService
from assessment_app.services.rag.public.models import RagIngestionResult

logger = logging.getLogger(__name__)


class DefaultRagIngestionService:
    """Orchestrate all ingestion stages through service-owned ports."""

    def __init__(
        self,
        parsing_service: DefaultIngestionParsingService,
        chunking_service: DefaultSemanticChunkingService,
        graph_builder: GraphBuilder,
        graph_store: GraphStore,
        vector_store: RagVectorStore,
    ) -> None:
        self._parsing_service = parsing_service
        self._chunking_service = chunking_service
        self._graph_builder = graph_builder
        self._graph_store = graph_store
        self._vector_store = vector_store
        self._lock = threading.Lock()

    def rebuild(self) -> RagIngestionResult:
        """Rebuild parsed sections, SQLite graph maps, and Chroma vectors."""
        with self._lock:
            logger.info("Starting ingestion rebuild")
            logger.info("Stage 1: Parsing document into hierarchical sections...")
            sections = self._parsing_service.parse()
            logger.info("Parsed %d sections.", len(sections))
            
            logger.info("Stage 2: Chunking sections semantically...")
            chunks = self._chunking_service.chunk(sections)
            logger.info("Generated %d chunks.", len(chunks))
            
            logger.info("Stage 3: Building graph navigation maps...")
            graph = self._graph_builder.build(sections, chunks)
            logger.info("Built graph with %d chunk nodes.", len(graph.chunks))
            
            logger.info("Stage 4: Persisting graph to SQLite...")
            self._graph_store.replace_graph(graph)
            
            logger.info("Stage 5: Persisting embeddings to ChromaDB...")
            self._vector_store.replace_chunks(chunks, graph)
            
            logger.info("Ingestion rebuild complete.")

        return RagIngestionResult(
            section_count=len(sections),
            chunk_count=len(chunks),
            graph_chunk_count=len(graph.chunks),
            vector_count=self._vector_store.count(),
        )


_: RagIngestionService = DefaultRagIngestionService.__new__(DefaultRagIngestionService)  # type: ignore[assignment]

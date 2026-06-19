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
from assessment_app.services.rag.public.models import GraphEdge, GraphNode, GraphVisualization, RagIngestionResult

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

    def get_graph_visualization(self, offset: int = 0, limit: int = 5000) -> GraphVisualization:
        """Load stored graph maps and shape them for the frontend."""
        graph = self._graph_store.load_graph()
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        safe_offset = max(0, offset)
        safe_limit = max(1, min(limit, 5000))

        for section in graph.sections.values():
            nodes.append(
                GraphNode(
                    id=section.id,
                    label=_section_label(section.id, section.title),
                    kind="section",
                    parent_id=section.parent,
                    section_id=section.id,
                    text_preview=None,
                )
            )

        for chunk_id, chunk in graph.chunks.items():
            nodes.append(
                GraphNode(
                    id=chunk_id,
                    label=chunk_id,
                    kind="chunk",
                    parent_id=chunk.section_id,
                    section_id=chunk.section_id,
                    text_preview=_preview(chunk.text),
                )
            )
            edges.append(GraphEdge(source=chunk.section_id, target=chunk_id, kind="contains"))

        for parent_id, child_ids in graph.section_hierarchy.items():
            for child_id in child_ids:
                edges.append(GraphEdge(source=parent_id, target=child_id, kind="section_child"))

        for chunk_id, next_chunk_id in graph.chunk_sequence.items():
            if next_chunk_id:
                edges.append(GraphEdge(source=chunk_id, target=next_chunk_id, kind="next_chunk"))

        for chunk_id, referenced_section_ids in graph.chunk_references.items():
            for section_id in referenced_section_ids:
                edges.append(GraphEdge(source=chunk_id, target=section_id, kind="references"))

        visible_nodes = nodes[safe_offset : safe_offset + safe_limit]
        visible_node_ids = {node.id for node in visible_nodes}
        visible_edges = [
            edge
            for edge in edges
            if edge.source in visible_node_ids and edge.target in visible_node_ids
        ]

        return GraphVisualization(
            sections_count=len(graph.sections),
            chunks_count=len(graph.chunks),
            references_count=sum(len(values) for values in graph.chunk_references.values()),
            total_nodes=len(nodes),
            total_edges=len(edges),
            offset=safe_offset,
            limit=safe_limit,
            nodes=visible_nodes,
            edges=visible_edges,
        )


def _section_label(section_id: str, title: str) -> str:
    if section_id == "front_matter":
        return "Front Matter"
    section_number = section_id.replace("section_", "").replace("_", ".")
    return f"{section_number} {title}".strip()


def _preview(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}..."


_: RagIngestionService = DefaultRagIngestionService.__new__(DefaultRagIngestionService)  # type: ignore[assignment]

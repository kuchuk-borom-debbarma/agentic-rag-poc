"""Unit tests for RAG ingestion orchestration."""

from assessment_app.services.rag.internal.ingestion.graph_builder import GraphBuilder
from assessment_app.services.rag.internal.ingestion.models import ChunkedContent, GraphMaps, Section
from assessment_app.services.rag.internal.service_impl import DefaultRagIngestionService


def test_rag_ingestion_service_rebuilds_all_stages_in_order():
    calls: list[str] = []
    sections = [Section(id="section_1", title="Terms", parent=None, layout=[])]
    chunks = [ChunkedContent("section_1", 0, 0, "Terms content.", [], [1.0, 0.0])]
    graph = GraphBuilder().build(sections, chunks)

    service = DefaultRagIngestionService(
        parsing_service=_ParsingService(calls, sections),
        chunking_service=_ChunkingService(calls, chunks),
        graph_builder=_GraphBuilder(calls, graph),
        graph_store=_GraphStore(calls),
        vector_store=_VectorStore(calls, vector_count=1),
    )

    result = service.rebuild()

    assert calls == ["parse", "chunk", "build_graph", "replace_graph", "replace_chunks", "count_vectors"]
    assert result.section_count == 1
    assert result.chunk_count == 1
    assert result.graph_chunk_count == 1
    assert result.vector_count == 1


class _ParsingService:
    def __init__(self, calls: list[str], sections: list[Section]) -> None:
        self._calls = calls
        self._sections = sections

    def parse(self) -> list[Section]:
        self._calls.append("parse")
        return self._sections


class _ChunkingService:
    def __init__(self, calls: list[str], chunks: list[ChunkedContent]) -> None:
        self._calls = calls
        self._chunks = chunks

    def chunk(self, sections: list[Section]) -> list[ChunkedContent]:
        self._calls.append("chunk")
        return self._chunks


class _GraphBuilder:
    def __init__(self, calls: list[str], graph: GraphMaps) -> None:
        self._calls = calls
        self._graph = graph

    def build(self, sections: list[Section], chunks: list[ChunkedContent]) -> GraphMaps:
        self._calls.append("build_graph")
        return self._graph


class _GraphStore:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def replace_graph(self, graph: GraphMaps) -> None:
        self._calls.append("replace_graph")

    def load_graph(self) -> GraphMaps:
        raise NotImplementedError


class _VectorStore:
    def __init__(self, calls: list[str], vector_count: int) -> None:
        self._calls = calls
        self._vector_count = vector_count

    def replace_chunks(self, chunks: list[ChunkedContent], graph: GraphMaps) -> None:
        self._calls.append("replace_chunks")

    def count(self) -> int:
        self._calls.append("count_vectors")
        return self._vector_count

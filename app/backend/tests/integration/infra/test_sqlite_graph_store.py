"""Integration tests for SQLite-backed graph-map storage."""

import sqlite3

from assessment_app.infra.sqlite.sqlite_graph_store import SqliteGraphStore
from assessment_app.services.rag.internal.ingestion.models import (
    ChunkedContent,
    ContentBlock,
    GraphMaps,
    Reference,
    Section,
    SectionRefBlock,
)


def test_sqlite_graph_store_round_trips_graph_maps(tmp_path):
    store = SqliteGraphStore(tmp_path / "graph.db")
    graph = _graph()

    store.replace_graph(graph)
    loaded = store.load_graph()

    assert loaded.section_hierarchy == graph.section_hierarchy
    assert loaded.chunk_sequence == graph.chunk_sequence
    assert loaded.chunk_to_section == graph.chunk_to_section
    assert loaded.chunk_references == graph.chunk_references
    assert loaded.sections == graph.sections
    assert loaded.chunks == _without_embeddings(graph.chunks)


def test_sqlite_graph_store_replace_graph_clears_stale_rows(tmp_path):
    store = SqliteGraphStore(tmp_path / "graph.db")
    store.replace_graph(_graph())
    fresh_graph = GraphMaps(
        section_hierarchy={"section_3": []},
        chunk_sequence={"section_3:0:0": None},
        chunk_to_section={"section_3:0:0": "section_3"},
        chunk_references={"section_3:0:0": []},
        sections={"section_3": Section(id="section_3", title="Fresh", parent=None, layout=[])},
        chunks={"section_3:0:0": ChunkedContent("section_3", 0, 0, "Fresh", [], [3.0])},
    )

    store.replace_graph(fresh_graph)
    loaded = store.load_graph()

    assert loaded.sections == fresh_graph.sections
    assert loaded.chunks == _without_embeddings(fresh_graph.chunks)
    assert "section_1" not in loaded.sections
    assert "section_1:0:0" not in loaded.chunks


def test_sqlite_graph_store_recreates_legacy_embedding_schema(tmp_path):
    sqlite_path = tmp_path / "graph.db"
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(
            """
            CREATE TABLE graph_chunks (
                chunk_id TEXT PRIMARY KEY,
                section_id TEXT NOT NULL,
                layout_index INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )

    SqliteGraphStore(sqlite_path)

    with sqlite3.connect(sqlite_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(graph_chunks)").fetchall()]

    assert "embedding_json" not in columns


def _without_embeddings(chunks: dict[str, ChunkedContent]) -> dict[str, ChunkedContent]:
    return {
        chunk_id: ChunkedContent(
            section_id=chunk.section_id,
            layout_index=chunk.layout_index,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            references=chunk.references,
        )
        for chunk_id, chunk in chunks.items()
    }


def _graph() -> GraphMaps:
    sections = {
        "section_1": Section(
            id="section_1",
            title="Foo",
            parent=None,
            layout=[
                ContentBlock(
                    data="See Bar.",
                    references=[Reference("section_2", 4, 7)],
                ),
                SectionRefBlock("section_2"),
            ],
        ),
        "section_2": Section(id="section_2", title="Bar", parent="section_1", layout=[ContentBlock("Bar")]),
    }
    chunks = {
        "section_1:0:0": ChunkedContent(
            section_id="section_1",
            layout_index=0,
            chunk_index=0,
            text="See Bar.",
            references=[Reference("section_2", 4, 7)],
            embedding=[0.1, 0.2],
        ),
        "section_2:0:0": ChunkedContent(
            section_id="section_2",
            layout_index=0,
            chunk_index=0,
            text="Bar",
            references=[],
            embedding=[0.3, 0.4],
        ),
    }
    return GraphMaps(
        section_hierarchy={"section_1": ["section_2"], "section_2": []},
        chunk_sequence={"section_1:0:0": None, "section_2:0:0": None},
        chunk_to_section={"section_1:0:0": "section_1", "section_2:0:0": "section_2"},
        chunk_references={"section_1:0:0": ["section_2"], "section_2:0:0": []},
        sections=sections,
        chunks=chunks,
    )

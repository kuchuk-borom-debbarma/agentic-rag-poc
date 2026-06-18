"""SQLite-backed storage for lightweight RAG graph maps."""

from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from pathlib import Path
from typing import Any

from assessment_app.services.rag.internal.ingestion.models import (
    ChunkedContent,
    ContentBlock,
    GraphMaps,
    Reference,
    Section,
    SectionRefBlock,
)


from assessment_app.services.query.public.models import SourceSnippet

class SqliteGraphStore:
    """Persist graph maps in one local SQLite file."""

    def __init__(self, sqlite_path: Path) -> None:
        self._sqlite_path = sqlite_path
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_chunk(self, chunk_id: str) -> SourceSnippet | None:
        """Fetch a specific chunk by ID."""
        chunks = self._fetch_snippets([chunk_id], "semantic")
        return chunks[0] if chunks else None

    def get_neighbors(self, chunk_ids: list[str], neighbors: int = 1) -> list[SourceSnippet]:
        """Fetch chunks immediately surrounding the given chunks."""
        if not chunk_ids:
            return []
        
        # We fetch neighbors using layout_index and chunk_index sorting for simplicity.
        # Alternatively, use graph_chunk_sequence, but sequence is a linked list which is hard in basic SQL.
        # Let's fetch adjacent chunks in the same layout order.
        neighbor_ids = set()
        with self._connect() as conn:
            for cid in chunk_ids:
                row = conn.execute("SELECT section_id, layout_index, chunk_index FROM graph_chunks WHERE chunk_id = ?", (cid,)).fetchone()
                if not row:
                    continue
                # Simple approximation: fetch chunks close in layout_index/chunk_index.
                # A robust way is to just query ordering by layout_index, chunk_index.
                # Actually, let's use a simpler bounded query.
                pass
        
        # Better: use chunk_sequence.
        # prev chunk: chunk_id WHERE next_chunk_id = ?
        # next chunk: next_chunk_id WHERE chunk_id = ?
        with self._connect() as conn:
            for cid in chunk_ids:
                for _ in range(neighbors):
                    prev = conn.execute("SELECT chunk_id FROM graph_chunk_sequence WHERE next_chunk_id = ?", (cid,)).fetchone()
                    if prev:
                        neighbor_ids.add(prev["chunk_id"])
                    nxt = conn.execute("SELECT next_chunk_id FROM graph_chunk_sequence WHERE chunk_id = ?", (cid,)).fetchone()
                    if nxt and nxt["next_chunk_id"]:
                        neighbor_ids.add(nxt["next_chunk_id"])
        
        return self._fetch_snippets(list(neighbor_ids), "neighbor")

    def get_section_chunks(self, section_numbers: list[str]) -> list[SourceSnippet]:
        """Fetch all chunks belonging to specified section numbers."""
        if not section_numbers:
            return []
        # We need to map section_number (e.g. "2.2") to section_id (e.g. "section_2_2")
        # For robustness, we search by title or ID.
        section_ids = [f"section_{n.replace('.', '_')}" for n in section_numbers]
        with self._connect() as conn:
            placeholders = ",".join("?" * len(section_ids))
            rows = conn.execute(f"SELECT chunk_id FROM graph_chunks WHERE section_id IN ({placeholders})", section_ids).fetchall()
        return self._fetch_snippets([row["chunk_id"] for row in rows], "exact_section")

    def get_referenced_sections(self, chunk_ids: list[str], limit: int = 2) -> list[SourceSnippet]:
        """Fetch the first N chunks from sections referenced by the given chunks."""
        if not chunk_ids:
            return []
        referenced_section_ids = set()
        with self._connect() as conn:
            placeholders = ",".join("?" * len(chunk_ids))
            rows = conn.execute(f"SELECT referenced_section_id FROM graph_chunk_references WHERE chunk_id IN ({placeholders})", chunk_ids).fetchall()
            for row in rows:
                referenced_section_ids.add(row["referenced_section_id"])
        
        if not referenced_section_ids:
            return []
            
        result_chunk_ids = []
        with self._connect() as conn:
            for sid in referenced_section_ids:
                rows = conn.execute("SELECT chunk_id FROM graph_chunks WHERE section_id = ? ORDER BY layout_index, chunk_index LIMIT ?", (sid, limit)).fetchall()
                result_chunk_ids.extend([row["chunk_id"] for row in rows])
                
        return self._fetch_snippets(result_chunk_ids, "reference")

    def get_parent_sections(self, chunk_ids: list[str]) -> list[SourceSnippet]:
        """Fetch chunks from the parent sections of the given chunks."""
        if not chunk_ids:
            return []
        parent_section_ids = set()
        with self._connect() as conn:
            placeholders = ",".join("?" * len(chunk_ids))
            rows = conn.execute(f"""
                SELECT s.parent_section_id 
                FROM graph_chunks c
                JOIN graph_sections s ON c.section_id = s.section_id
                WHERE c.chunk_id IN ({placeholders})
            """, chunk_ids).fetchall()
            for row in rows:
                if row["parent_section_id"]:
                    parent_section_ids.add(row["parent_section_id"])
        
        if not parent_section_ids:
            return []
        
        result_chunk_ids = []
        with self._connect() as conn:
            for sid in parent_section_ids:
                rows = conn.execute("SELECT chunk_id FROM graph_chunks WHERE section_id = ? ORDER BY layout_index, chunk_index", (sid,)).fetchall()
                result_chunk_ids.extend([row["chunk_id"] for row in rows])
        
        return self._fetch_snippets(result_chunk_ids, "parent")

    def get_child_sections(self, chunk_ids: list[str]) -> list[SourceSnippet]:
        """Fetch chunks from the child sections of the given chunks."""
        if not chunk_ids:
            return []
        child_section_ids = set()
        with self._connect() as conn:
            placeholders = ",".join("?" * len(chunk_ids))
            rows = conn.execute(f"""
                SELECT h.child_section_id 
                FROM graph_chunks c
                JOIN graph_section_hierarchy h ON c.section_id = h.parent_section_id
                WHERE c.chunk_id IN ({placeholders})
            """, chunk_ids).fetchall()
            for row in rows:
                child_section_ids.add(row["child_section_id"])
        
        if not child_section_ids:
            return []
            
        result_chunk_ids = []
        with self._connect() as conn:
            for sid in child_section_ids:
                rows = conn.execute("SELECT chunk_id FROM graph_chunks WHERE section_id = ? ORDER BY layout_index, chunk_index", (sid,)).fetchall()
                result_chunk_ids.extend([row["chunk_id"] for row in rows])
                
        return self._fetch_snippets(result_chunk_ids, "child")

    def _fetch_snippets(self, chunk_ids: list[str], source_type: str) -> list[SourceSnippet]:
        if not chunk_ids:
            return []
        
        with self._connect() as conn:
            placeholders = ",".join("?" * len(chunk_ids))
            query = f"""
                SELECT 
                    c.chunk_id, c.text, c.section_id, c.layout_index, c.chunk_index,
                    s.title AS section_title, s.parent_section_id,
                    ps.title AS parent_section_title
                FROM graph_chunks c
                JOIN graph_sections s ON c.section_id = s.section_id
                LEFT JOIN graph_sections ps ON s.parent_section_id = ps.section_id
                WHERE c.chunk_id IN ({placeholders})
                ORDER BY c.layout_index, c.chunk_index
            """
            rows = conn.execute(query, chunk_ids).fetchall()
            
            snippets = []
            for row in rows:
                cid = row["chunk_id"]
                ref_rows = conn.execute("SELECT referenced_section_id FROM graph_chunk_references WHERE chunk_id = ?", (cid,)).fetchall()
                refs = [r["referenced_section_id"] for r in ref_rows]
                
                # Derive section_number from section_id (e.g. section_2_2 -> 2.2)
                sid = row["section_id"]
                snum = sid.replace("section_", "").replace("_", ".") if sid.startswith("section_") else sid
                
                pid = row["parent_section_id"]
                pnum = pid.replace("section_", "").replace("_", ".") if pid and pid.startswith("section_") else pid
                
                snippets.append(SourceSnippet(
                    chunk_id=cid,
                    text=row["text"],
                    page_start=0,
                    page_end=0,
                    source_file="AWS Customer Agreement.pdf",
                    section_id=sid,
                    section_number=snum,
                    section_title=row["section_title"],
                    parent_section_id=pid,
                    parent_section_number=pnum,
                    parent_section_title=row["parent_section_title"],
                    order=row["layout_index"] * 1000 + row["chunk_index"],
                    referenced_section_ids=refs,
                    source_type=source_type
                ))
            return snippets

    def replace_graph(self, graph: GraphMaps) -> None:
        """Atomically replace all stored graph maps."""
        with self._connect() as conn:
            conn.execute("BEGIN")
            self._clear(conn)
            self._insert_sections(conn, graph)
            self._insert_chunks(conn, graph)
            self._insert_section_hierarchy(conn, graph)
            self._insert_chunk_sequence(conn, graph)
            self._insert_chunk_references(conn, graph)
            conn.commit()

    def load_graph(self) -> GraphMaps:
        """Load graph maps from SQLite."""
        with self._connect() as conn:
            sections = {
                row["section_id"]: _section_from_payload(json.loads(row["payload_json"]))
                for row in conn.execute("SELECT section_id, payload_json FROM graph_sections")
            }
            chunks = {
                row["chunk_id"]: _chunk_from_payload(json.loads(row["payload_json"]))
                for row in conn.execute("SELECT chunk_id, payload_json FROM graph_chunks")
            }
            section_hierarchy = {section_id: [] for section_id in sections}
            for row in conn.execute(
                """
                SELECT parent_section_id, child_section_id
                FROM graph_section_hierarchy
                ORDER BY parent_section_id, position
                """
            ):
                section_hierarchy.setdefault(row["parent_section_id"], []).append(row["child_section_id"])

            chunk_sequence = {
                row["chunk_id"]: row["next_chunk_id"]
                for row in conn.execute("SELECT chunk_id, next_chunk_id FROM graph_chunk_sequence")
            }
            chunk_to_section = {
                row["chunk_id"]: row["section_id"]
                for row in conn.execute("SELECT chunk_id, section_id FROM graph_chunks")
            }
            chunk_references = {chunk_id: [] for chunk_id in chunks}
            for row in conn.execute(
                """
                SELECT chunk_id, referenced_section_id
                FROM graph_chunk_references
                ORDER BY chunk_id, position
                """
            ):
                chunk_references.setdefault(row["chunk_id"], []).append(row["referenced_section_id"])

        return GraphMaps(
            section_hierarchy=section_hierarchy,
            chunk_sequence=chunk_sequence,
            chunk_to_section=chunk_to_section,
            chunk_references=chunk_references,
            sections=sections,
            chunks=chunks,
        )

    def _init_db(self) -> None:
        with self._connect() as conn:
            self._drop_legacy_graph_tables(conn)
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS graph_sections (
                    section_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    parent_section_id TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS graph_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    section_id TEXT NOT NULL,
                    layout_index INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS graph_section_hierarchy (
                    parent_section_id TEXT NOT NULL,
                    child_section_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY (parent_section_id, child_section_id)
                );

                CREATE TABLE IF NOT EXISTS graph_chunk_sequence (
                    chunk_id TEXT PRIMARY KEY,
                    next_chunk_id TEXT
                );

                CREATE TABLE IF NOT EXISTS graph_chunk_references (
                    chunk_id TEXT NOT NULL,
                    referenced_section_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY (chunk_id, referenced_section_id)
                );
                """
            )

    def _drop_legacy_graph_tables(self, conn: sqlite3.Connection) -> None:
        columns = conn.execute("PRAGMA table_info(graph_chunks)").fetchall()
        if not any(row["name"] == "embedding_json" for row in columns):
            return
        for table in (
            "graph_chunk_references",
            "graph_chunk_sequence",
            "graph_section_hierarchy",
            "graph_chunks",
            "graph_sections",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {table}")

    def _clear(self, conn: sqlite3.Connection) -> None:
        for table in (
            "graph_chunk_references",
            "graph_chunk_sequence",
            "graph_section_hierarchy",
            "graph_chunks",
            "graph_sections",
        ):
            conn.execute(f"DELETE FROM {table}")

    def _insert_sections(self, conn: sqlite3.Connection, graph: GraphMaps) -> None:
        conn.executemany(
            """
            INSERT INTO graph_sections (section_id, title, parent_section_id, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            [
                (section.id, section.title, section.parent, json.dumps(_section_payload(section)))
                for section in graph.sections.values()
            ],
        )

    def _insert_chunks(self, conn: sqlite3.Connection, graph: GraphMaps) -> None:
        conn.executemany(
            """
            INSERT INTO graph_chunks (
                chunk_id, section_id, layout_index, chunk_index, text, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk_id,
                    chunk.section_id,
                    chunk.layout_index,
                    chunk.chunk_index,
                    chunk.text,
                    json.dumps(_chunk_payload(chunk)),
                )
                for chunk_id, chunk in graph.chunks.items()
            ],
        )

    def _insert_section_hierarchy(self, conn: sqlite3.Connection, graph: GraphMaps) -> None:
        conn.executemany(
            """
            INSERT INTO graph_section_hierarchy (parent_section_id, child_section_id, position)
            VALUES (?, ?, ?)
            """,
            [
                (parent_id, child_id, position)
                for parent_id, child_ids in graph.section_hierarchy.items()
                for position, child_id in enumerate(child_ids)
            ],
        )

    def _insert_chunk_sequence(self, conn: sqlite3.Connection, graph: GraphMaps) -> None:
        conn.executemany(
            """
            INSERT INTO graph_chunk_sequence (chunk_id, next_chunk_id)
            VALUES (?, ?)
            """,
            list(graph.chunk_sequence.items()),
        )

    def _insert_chunk_references(self, conn: sqlite3.Connection, graph: GraphMaps) -> None:
        conn.executemany(
            """
            INSERT INTO graph_chunk_references (chunk_id, referenced_section_id, position)
            VALUES (?, ?, ?)
            """,
            [
                (chunk_id, section_id, position)
                for chunk_id, section_ids in graph.chunk_references.items()
                for position, section_id in enumerate(section_ids)
            ],
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn


def _section_payload(section: Section) -> dict[str, Any]:
    return {
        "id": section.id,
        "title": section.title,
        "parent": section.parent,
        "layout": [_layout_block_payload(block) for block in section.layout],
    }


def _layout_block_payload(block: ContentBlock | SectionRefBlock) -> dict[str, Any]:
    if isinstance(block, ContentBlock):
        return {
            "type": "content",
            "data": block.data,
            "references": [asdict(reference) for reference in block.references],
        }
    return {"type": "section-ref", "section_id": block.section_id}


def _chunk_payload(chunk: ChunkedContent) -> dict[str, Any]:
    return {
        "section_id": chunk.section_id,
        "layout_index": chunk.layout_index,
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "references": [asdict(reference) for reference in chunk.references],
    }


def _section_from_payload(payload: dict[str, Any]) -> Section:
    return Section(
        id=payload["id"],
        title=payload["title"],
        parent=payload["parent"],
        layout=[_layout_block_from_payload(block) for block in payload["layout"]],
    )


def _layout_block_from_payload(payload: dict[str, Any]) -> ContentBlock | SectionRefBlock:
    if payload["type"] == "content":
        return ContentBlock(
            data=payload["data"],
            references=[Reference(**reference) for reference in payload["references"]],
        )
    return SectionRefBlock(section_id=payload["section_id"])


def _chunk_from_payload(payload: dict[str, Any]) -> ChunkedContent:
    return ChunkedContent(
        section_id=payload["section_id"],
        layout_index=payload["layout_index"],
        chunk_index=payload["chunk_index"],
        text=payload["text"],
        references=[Reference(**reference) for reference in payload["references"]],
    )

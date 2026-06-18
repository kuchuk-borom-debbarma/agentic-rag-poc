"""ChromaDB implementation of VectorStore ports."""

from pathlib import Path
import json

import chromadb

from assessment_app.services.rag.public.models import DocumentChunk
from assessment_app.services.query.public.models import SourceSnippet


class ChromaVectorStore:
    """Persistent ChromaDB-backed vector store.

    Implements query and future indexing VectorStore port contracts through
    structural subtyping (Protocol). No explicit base class needed.
    """

    def __init__(self, persist_dir: Path, collection_name: str) -> None:
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._persist_dir))
        self._collection = self._client.get_or_create_collection(name=self._collection_name)

    # ── Index write methods ──────────────────────────────────────────────────

    def reset(self) -> None:
        """Delete and recreate the collection before rebuilding the index."""
        try:
            self._client.delete_collection(self._collection_name)
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(name=self._collection_name)

    def add_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        """Persist chunks and their pre-computed embeddings."""
        if not chunks:
            return
        self._collection.add(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "source_file": chunk.source_file,
                    "section_id": chunk.section_id,
                    "section_number": chunk.section_number,
                    "section_title": chunk.section_title,
                    "parent_section_id": chunk.parent_section_id or "",
                    "parent_section_number": chunk.parent_section_number or "",
                    "parent_section_title": chunk.parent_section_title or "",
                    "order": chunk.order,
                    "previous_chunk_id": chunk.previous_chunk_id or "",
                    "next_chunk_id": chunk.next_chunk_id or "",
                    "referenced_section_ids": json.dumps(chunk.referenced_section_ids),
                }
                for chunk in chunks
            ],
        )

    # ── Query port methods ───────────────────────────────────────────────────

    def search(self, query_embedding: list[float], top_k: int) -> list[SourceSnippet]:
        """Semantic nearest-neighbour search."""
        result = self._collection.query(query_embeddings=[query_embedding], n_results=top_k)
        return self._to_snippets(
            ids=result.get("ids", [[]])[0],
            documents=result.get("documents", [[]])[0],
            metadatas=result.get("metadatas", [[]])[0],
            distances=result.get("distances", [[]])[0],
            source_type="semantic",
        )

    def get_neighbors(self, orders: list[int], before: int, after: int) -> list[SourceSnippet]:
        """Fetch chunks within a window around matched orders."""
        if not orders or (before == 0 and after == 0):
            return []
        rows = self._all_snippets(source_type="neighbor")
        windows = [(order - before, order + after) for order in orders]
        return [row for row in rows if any(start <= row.order <= end for start, end in windows)]

    def get_section_chunks(self, section_numbers: list[str]) -> list[SourceSnippet]:
        """Fetch all chunks belonging to specified section numbers."""
        if not section_numbers:
            return []
        targets = set(section_numbers)
        return [row for row in self._all_snippets(source_type="exact_section") if row.section_number in targets]

    def get_referenced_sections(self, chunk_ids: list[str], max_chunks_per_section: int = 2) -> list[SourceSnippet]:
        """Fetch chunks from sections referenced by source chunks."""
        if not chunk_ids:
            return []
        chunks_by_id = {row.chunk_id: row for row in self._all_snippets(source_type="reference_seed")}
        referenced_section_ids = {
            section_id
            for chunk_id in chunk_ids
            for section_id in self._references_for(chunks_by_id, chunk_id)
        }
        if not referenced_section_ids:
            return []

        selected: list[SourceSnippet] = []
        counts: dict[str, int] = {}
        for row in self._all_snippets(source_type="reference"):
            if row.section_id not in referenced_section_ids:
                continue
            count = counts.get(row.section_id, 0)
            if count >= max_chunks_per_section:
                continue
            selected.append(row)
            counts[row.section_id] = count + 1
        return selected

    def count(self) -> int:
        """Return total stored chunk count."""
        return self._collection.count()

    # ── Private helpers ──────────────────────────────────────────────────────

    def _all_snippets(self, source_type: str) -> list[SourceSnippet]:
        result = self._collection.get(include=["documents", "metadatas"])
        snippets = self._to_snippets(
            ids=result.get("ids", []),
            documents=result.get("documents", []),
            metadatas=result.get("metadatas", []),
            distances=[],
            source_type=source_type,
        )
        return sorted(snippets, key=lambda row: row.order)

    def _to_snippets(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
        distances: list[float],
        source_type: str,
    ) -> list[SourceSnippet]:
        snippets = []
        for index, chunk_id in enumerate(ids):
            metadata = metadatas[index] or {}
            snippets.append(
                SourceSnippet(
                    chunk_id=chunk_id,
                    text=documents[index],
                    page_start=int(metadata.get("page_start", 0)),
                    page_end=int(metadata.get("page_end", 0)),
                    source_file=str(metadata.get("source_file", "")),
                    section_id=str(metadata.get("section_id", "")),
                    section_number=str(metadata.get("section_number", "")),
                    section_title=str(metadata.get("section_title", "")),
                    parent_section_id=self._optional(metadata.get("parent_section_id")),
                    parent_section_number=self._optional(metadata.get("parent_section_number")),
                    parent_section_title=self._optional(metadata.get("parent_section_title")),
                    order=int(metadata.get("order", 0)),
                    referenced_section_ids=json.loads(str(metadata.get("referenced_section_ids") or "[]")),
                    source_type=source_type,
                    score=float(distances[index]) if distances else None,
                )
            )
        return snippets

    def _optional(self, value: object) -> str | None:
        text = str(value or "")
        return text or None

    def _references_for(self, chunks_by_id: dict[str, SourceSnippet], chunk_id: str) -> list[str]:
        chunk = chunks_by_id.get(chunk_id)
        return chunk.referenced_section_ids if chunk else []

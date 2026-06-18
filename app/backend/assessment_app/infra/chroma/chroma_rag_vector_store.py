"""ChromaDB adapter for Stage 4 RAG chunk vectors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from assessment_app.services.rag.internal.ingestion.models import ChunkedContent, GraphMaps, VectorMatch


class ChromaRagVectorStore:
    """Persist Stage 2 chunk embeddings using LangChain's Chroma integration."""

    def __init__(self, persist_dir: Path, collection_name: str, embedding_function: Embeddings) -> None:
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._store = Chroma(
            collection_name=collection_name,
            persist_directory=str(persist_dir),
            embedding_function=embedding_function,
            collection_metadata={"hnsw:space": "cosine"}
        )

    def replace_chunks(self, chunks: list[ChunkedContent], graph: GraphMaps) -> None:
        """Replace all chunk vectors with the current ingestion run."""
        self._reset()
        if not chunks:
            return

        ids = [_chunk_id(chunk) for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        embeddings = [chunk.embedding for chunk in chunks]
        metadatas = [self._metadata(chunk, graph) for chunk in chunks]

        self._store._collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

    def search(self, query_embedding: list[float], top_k: int) -> list[tuple[str, float]]:
        """Search persisted chunk vectors by cosine distance. Satisfies SemanticStore."""
        count = self.count()
        if count == 0 or top_k <= 0:
            return []
        
        results = self._store.similarity_search_by_vector_with_relevance_scores(
            embedding=query_embedding, k=min(top_k, count)
        )
        return [(doc.metadata.get("id", ""), score) for doc, score in results]

    def search_by_embedding(self, embedding: list[float], top_k: int) -> list[VectorMatch]:
        """Search persisted chunk vectors by cosine distance."""
        count = self.count()
        if count == 0 or top_k <= 0:
            return []
            
        results = self._store.similarity_search_by_vector_with_relevance_scores(
            embedding=embedding, k=min(top_k, count)
        )
        return [
            self._match(
                chunk_id=doc.metadata.get("id", ""), # LangChain Chroma doesn't expose ID easily in Document without some hacking, wait!
                text=doc.page_content,
                metadata=doc.metadata,
                score=score
            )
            for doc, score in results
        ]

    def count(self) -> int:
        """Return total stored chunk vectors."""
        # Chroma LangChain wrapper doesn't have count directly, we access the underlying collection
        return self._store._collection.count()

    def _reset(self) -> None:
        self._store.delete_collection()
        # Re-initialize
        self._store = Chroma(
            collection_name=self._collection_name,
            persist_directory=str(self._persist_dir),
            embedding_function=self._store.embeddings,
            collection_metadata={"hnsw:space": "cosine"}
        )

    def _metadata(self, chunk: ChunkedContent, graph: GraphMaps) -> dict[str, Any]:
        section = graph.sections[chunk.section_id]
        return {
            "id": _chunk_id(chunk), # Inject ID so we can get it back
            "section_id": chunk.section_id,
            "parent_section_id": section.parent or "",
            "layout_index": chunk.layout_index,
            "chunk_index": chunk.chunk_index,
            "referenced_section_ids": json.dumps(graph.chunk_references.get(_chunk_id(chunk), [])),
        }

    def _match(self, chunk_id: str, text: str, metadata: dict[str, Any], score: float) -> VectorMatch:
        return VectorMatch(
            chunk_id=chunk_id,
            text=text,
            score=score,
            section_id=str(metadata.get("section_id", "")),
            parent_section_id=_optional(metadata.get("parent_section_id")),
            layout_index=int(metadata.get("layout_index", 0)),
            chunk_index=int(metadata.get("chunk_index", 0)),
            referenced_section_ids=json.loads(str(metadata.get("referenced_section_ids") or "[]")),
        )


def _chunk_id(chunk: ChunkedContent) -> str:
    return f"{chunk.section_id}:{chunk.layout_index}:{chunk.chunk_index}"


def _optional(value: object) -> str | None:
    text = str(value or "")
    return text or None

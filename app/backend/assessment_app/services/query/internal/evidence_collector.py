"""Evidence collector: lazy topological retrieval and deduplication.

Internal to the query bounded context. Not accessible from outside.
"""

from dataclasses import replace
from assessment_app.services.query.public.models import (
    RetrievalQuery,
    RetrievalStepTrace,
    SourceSnippet,
    TraceCandidate,
    VerificationResult,
)
from assessment_app.services.query.internal.ports import Embeddings, GraphStore, SemanticStore

_SOURCE_TYPE_PRIORITY: dict[str, int] = {
    "exact_section": 0,
    "semantic": 1,
    "parent": 2,
    "child": 3,
    "neighbor": 4,
    "reference": 5,
}

class EvidenceCollector:
    """Collect and deduplicate evidence lazily based on reflection.
    
    Provides methods for atomic initial search and topological expansion.
    """

    def __init__(
        self,
        embedding_client: Embeddings,
        semantic_store: SemanticStore,
        graph_store: GraphStore,
        top_k: int,
    ) -> None:
        self._embedding_client = embedding_client
        self._semantic_store = semantic_store
        self._graph_store = graph_store
        self._top_k = top_k
        self.last_trace_step: RetrievalStepTrace | None = None
        self.last_expansion_actions: list[str] = []

    def initial_search(
        self,
        retrieval_query: RetrievalQuery,
        top_k: int | None = None,
        original_query: str | None = None,
    ) -> list[SourceSnippet]:
        """Perform an atomic semantic and exact-section search for a single sub-query."""
        snippets: list[SourceSnippet] = []
        original_text = original_query or retrieval_query.query
        
        # 1. Exact sections
        if retrieval_query.target_sections:
            snippets.extend(
                replace(snippet, source_type="exact_section")
                for snippet in self._graph_store.get_section_chunks(retrieval_query.target_sections)
            )
            
        # UI ENHANCEMENT: Section 12 Definition Boost
        if any(term in original_text.lower() for term in ("define", "defined", "definition", "meaning", "means", "identical", "same", "what is", "what are", "difference", "entities")):
            snippets.extend(
                replace(snippet, source_type="exact_section")
                for snippet in self._graph_store.get_section_chunks(["12"])
            )

        # 2. Semantic search
        query_embedding = self._embedding_client.embed_query(retrieval_query.query)
        semantic_hits = self._semantic_store.search(query_embedding, top_k or self._top_k)
        
        vector_candidates: list[SourceSnippet] = []
        for chunk_id, score in semantic_hits:
            chunk = self._graph_store.get_chunk(chunk_id)
            if chunk:
                candidate = replace(chunk, source_type="semantic", score=round(score, 3))
                vector_candidates.append(candidate)
                snippets.append(candidate)
                
        deduped = self._dedupe(snippets)

        # UI ENHANCEMENT: Traces
        self.last_trace_step = RetrievalStepTrace(
            query_id=retrieval_query.query_id,
            query=retrieval_query.query,
            expanded_query=retrieval_query.query,
            explicit_sections=[],
            validated_sections=retrieval_query.target_sections,
            vector_candidates=self._trace_candidates(vector_candidates),
            lexical_candidates=[],
            reranked_candidates=self._trace_candidates(deduped),
            verifier=None,
            expansion_actions=[],
        )

        return deduped

    def expand_context(self, current_snippets: list[SourceSnippet], verification_result: VerificationResult) -> list[SourceSnippet]:
        """Expand the context topology based strictly on LLM reflection feedback."""
        if not current_snippets:
            return []
            
        chunk_ids = [snippet.chunk_id for snippet in current_snippets]
        new_snippets = list(current_snippets)
        actions: list[str] = []
        
        if getattr(verification_result, 'needs_parents', False):
            new_snippets.extend(self._graph_store.get_parent_sections(chunk_ids))
            actions.append("parents")
            
        if getattr(verification_result, 'needs_children', False):
            new_snippets.extend(self._graph_store.get_child_sections(chunk_ids))
            actions.append("children")
            
        if getattr(verification_result, 'needs_neighbors', False):
            new_snippets.extend(self._graph_store.get_neighbors(chunk_ids, neighbors=1))
            actions.append("neighbors")
            
        if getattr(verification_result, 'needs_references', False):
            new_snippets.extend(self._graph_store.get_referenced_sections(chunk_ids, limit=2))
            actions.append("references")
            
        self.last_expansion_actions = actions
        return self._dedupe(new_snippets)

    def _dedupe(self, snippets: list[SourceSnippet]) -> list[SourceSnippet]:
        by_id: dict[str, SourceSnippet] = {}
        for snippet in snippets:
            existing = by_id.get(snippet.chunk_id)
            if not existing or self._priority(snippet) < self._priority(existing):
                by_id[snippet.chunk_id] = snippet
        return sorted(by_id.values(), key=lambda snippet: snippet.order)

    def _priority(self, snippet: SourceSnippet) -> int:
        return _SOURCE_TYPE_PRIORITY.get(snippet.source_type, 9)

    def _trace_candidates(self, snippets: list[SourceSnippet], limit: int = 8) -> list[TraceCandidate]:
        return [
            TraceCandidate(
                chunk_id=snippet.chunk_id,
                section_number=snippet.section_number,
                section_title=snippet.section_title,
                source_type=snippet.source_type,
                score=getattr(snippet, 'score', 0.0),
                text_preview=self._preview(snippet.text),
            )
            for snippet in snippets[:limit]
        ]

    def _preview(self, text: str, limit: int = 180) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return f"{compact[: limit - 1].rstrip()}..."

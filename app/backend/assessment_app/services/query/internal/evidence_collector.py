"""Evidence collector: lazy topological retrieval and deduplication.

Internal to the query bounded context. Not accessible from outside.
"""

from assessment_app.services.query.public.models import RetrievalQuery, SourceSnippet, VerificationResult
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

    def initial_search(self, retrieval_query: RetrievalQuery, top_k: int | None = None) -> list[SourceSnippet]:
        """Perform an atomic semantic and exact-section search for a single sub-query."""
        snippets: list[SourceSnippet] = []
        
        # 1. Exact sections
        if retrieval_query.target_sections:
            snippets.extend(self._graph_store.get_section_chunks(retrieval_query.target_sections))
            
        # 2. Semantic search
        query_embedding = self._embedding_client.embed_query(retrieval_query.query)
        semantic_hits = self._semantic_store.search(query_embedding, top_k or self._top_k)
        
        for chunk_id, _ in semantic_hits:
            chunk = self._graph_store.get_chunk(chunk_id)
            if chunk:
                snippets.append(chunk)
                
        return self._dedupe(snippets)

    def expand_context(self, current_snippets: list[SourceSnippet], verification_result: VerificationResult) -> list[SourceSnippet]:
        """Expand the context topology based strictly on LLM reflection feedback."""
        if not current_snippets:
            return []
            
        chunk_ids = [snippet.chunk_id for snippet in current_snippets]
        new_snippets = list(current_snippets)
        
        if getattr(verification_result, 'needs_parents', False):
            new_snippets.extend(self._graph_store.get_parent_sections(chunk_ids))
            
        if getattr(verification_result, 'needs_children', False):
            new_snippets.extend(self._graph_store.get_child_sections(chunk_ids))
            
        if getattr(verification_result, 'needs_neighbors', False):
            new_snippets.extend(self._graph_store.get_neighbors(chunk_ids, neighbors=1))
            
        if getattr(verification_result, 'needs_references', False):
            new_snippets.extend(self._graph_store.get_referenced_sections(chunk_ids, limit=2))
            
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

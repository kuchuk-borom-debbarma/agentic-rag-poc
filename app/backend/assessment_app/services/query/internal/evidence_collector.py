"""Evidence collector: lazy topological retrieval and deduplication.

Internal to the query bounded context. Not accessible from outside.
"""

from dataclasses import replace
import re

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
    "lexical": 1,
    "parent": 2,
    "child": 3,
    "neighbor": 4,
    "reference": 5,
}
_SECTION_RE = re.compile(r"\bsection\s+(\d+(?:\.\d+)*)\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
    "for", "from", "how", "if", "in", "is", "it", "of", "on", "or", "the",
    "this", "to", "under", "what", "when", "who", "will", "with",
}
_EXPANSIONS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("promise", "secure", "security"), "will implement reasonable appropriate measures secure Your Content accidental unlawful loss access disclosure"),
    (("ownership", "rights", "own"), "obtain no rights Your Content licensors consent use provide Services Section 6"),
    (("term", "start", "end", "effective date"), "term commence Effective Date remain in effect terminated Section 5"),
    (("notice", "discontinue", "change", "adverse"), "prior notice advance notice days discontinue material functionality Service Level Agreement"),
    (("terminate", "termination", "convenience", "cause"), "terminate termination Termination Date close account material breach Section 5"),
    (("suspend", "suspension"), "suspend access security risk liability risk fraudulent breach payment ordinary business operations"),
    (("fee", "fees", "bill", "payment"), "fees charges monthly bill payment add increase prior notice"),
    (("tax", "taxes"), "taxes governmental charges responsible identifying paying applicable law"),
    (("indemnify", "indemnification", "claim", "claims"), "defend indemnify hold harmless third party claims intellectual property infringement"),
    (("liability", "damages", "cap"), "liability indirect incidental consequential damages aggregate liability cap amounts paid"),
    (("assign", "assignment", "transfer"), "assign transfer prior written consent merger acquisition asset sale affiliate corporate reorganization"),
    (("warranty", "warranties", "disclaimer"), "provided as is disclaim warranties representations uninterrupted error free secure lost altered"),
)


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
        """Perform hybrid exact, lexical, and semantic search, then rerank."""
        final_limit = top_k or self._top_k
        candidate_limit = max(final_limit * 6, 30)
        original_text = original_query or retrieval_query.query
        expanded_query = _expand_query(f"{original_text} {retrieval_query.query}")
        explicit_sections = sorted(
            set(_extract_sections(original_text)) | set(_extract_sections(retrieval_query.query))
        )
        validated_sections = self._validated_target_sections(
            retrieval_query.target_sections,
            expanded_query,
            explicit_sections,
        )

        snippets: list[SourceSnippet] = []

        exact_sections = sorted(set(explicit_sections) | set(validated_sections))
        if exact_sections:
            snippets.extend(
                replace(snippet, source_type="exact_section")
                for snippet in self._graph_store.get_section_chunks(exact_sections)
            )

        query_embedding = self._embedding_client.embed_query(expanded_query)
        semantic_hits = self._semantic_store.search(query_embedding, candidate_limit)
        vector_candidates: list[SourceSnippet] = []
        for chunk_id, _ in semantic_hits:
            chunk = self._graph_store.get_chunk(chunk_id)
            if chunk:
                candidate = replace(chunk, source_type="semantic")
                vector_candidates.append(candidate)
                snippets.append(candidate)

        lexical_candidates = self._lexical_search(expanded_query, candidate_limit)
        snippets.extend(lexical_candidates)

        reranked = self._rerank(snippets, expanded_query, exact_sections, final_limit)
        self.last_trace_step = RetrievalStepTrace(
            query_id=retrieval_query.query_id,
            query=retrieval_query.query,
            expanded_query=expanded_query,
            explicit_sections=explicit_sections,
            validated_sections=validated_sections,
            vector_candidates=_trace_candidates(vector_candidates),
            lexical_candidates=_trace_candidates(lexical_candidates),
            reranked_candidates=_trace_candidates(reranked),
            verifier=None,
            expansion_actions=[],
        )
        return sorted(reranked, key=lambda snippet: snippet.order)

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

    def _lexical_search(self, query: str, limit: int) -> list[SourceSnippet]:
        search = getattr(self._graph_store, "search_lexical", None)
        if search is None:
            return []
        return list(search(query, limit))

    def _validated_target_sections(
        self,
        target_sections: list[str],
        expanded_query: str,
        explicit_sections: list[str],
    ) -> list[str]:
        explicit = set(explicit_sections)
        validated: list[str] = []
        query_tokens = _tokens(expanded_query)
        for raw_section in target_sections:
            section = _normalize_section(raw_section)
            if not section or section in validated:
                continue
            if section in explicit:
                validated.append(section)
                continue
            snippets = self._graph_store.get_section_chunks([section])
            if not snippets:
                continue
            section_text = " ".join(
                f"{snippet.section_number} {snippet.section_title} {snippet.parent_section_title or ''} {snippet.text}"
                for snippet in snippets
            )
            overlap = query_tokens & _tokens(section_text)
            title_overlap = query_tokens & _tokens(" ".join(snippet.section_title for snippet in snippets))
            if title_overlap and len(overlap) >= 2:
                validated.append(section)
        return validated

    def _rerank(
        self,
        snippets: list[SourceSnippet],
        expanded_query: str,
        exact_sections: list[str],
        limit: int,
    ) -> list[SourceSnippet]:
        deduped = self._dedupe(snippets)
        query_tokens = _tokens(expanded_query)
        scored = [
            (self._score(snippet, expanded_query, query_tokens, set(exact_sections)), snippet)
            for snippet in deduped
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            replace(snippet, score=round(score, 3))
            for score, snippet in scored[:limit]
        ]

    def _score(
        self,
        snippet: SourceSnippet,
        expanded_query: str,
        query_tokens: set[str],
        exact_sections: set[str],
    ) -> float:
        text = f"{snippet.section_number} {snippet.section_title} {snippet.parent_section_title or ''} {snippet.text}"
        text_tokens = _tokens(text)
        overlap = query_tokens & text_tokens
        score = float(len(overlap) * 5)
        source_bonus = {
            "exact_section": 70.0,
            "lexical": 35.0,
            "semantic": 12.0,
            "parent": 8.0,
            "child": 8.0,
            "neighbor": 5.0,
            "reference": 5.0,
        }.get(snippet.source_type, 0.0)
        score += source_bonus
        if snippet.section_number in exact_sections:
            score += 45.0
        if _tokens(snippet.section_title) & query_tokens:
            score += 12.0
        normalized_text = " ".join(_tokens(text))
        for phrase in (
            "your content",
            "effective date",
            "remain in effect",
            "obtain no rights",
            "reasonable appropriate measures",
            "termination date",
        ):
            if phrase in expanded_query.lower() and all(part in normalized_text for part in phrase.split()):
                score += 18.0
        if snippet.section_number in {"5.1", "6.1", "1.3"}:
            if _intent_matches_key_clause(expanded_query, snippet.section_number):
                score += 70.0
        if snippet.section_number == "front.matter" and "front matter" not in expanded_query.lower():
            score -= 45.0
        if _asks_security(expanded_query) and snippet.section_number == "6.1":
            score -= 120.0
        if _asks_ownership(expanded_query) and snippet.section_number == "1.3":
            score -= 120.0
        if _asks_affirmative_obligation(expanded_query) and snippet.section_number in {"8", "9.1", "11.15"}:
            score -= 30.0
        return score


def _extract_sections(text: str) -> list[str]:
    return [_normalize_section(match.group(1)) for match in _SECTION_RE.finditer(text) if _normalize_section(match.group(1))]


def _normalize_section(value: str) -> str:
    return value.strip().lower().replace("section", "").strip().strip(".")


def _tokens(value: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(value.lower()) if token not in _STOP_WORDS and len(token) > 1}


def _expand_query(query: str) -> str:
    lower = query.lower()
    tokens = _tokens(query)
    expansions = [query]
    for triggers, expansion in _EXPANSIONS:
        if any(_trigger_matches(trigger, lower, tokens) for trigger in triggers):
            expansions.append(expansion)
    return " ".join(dict.fromkeys(" ".join(expansions).split()))


def _trigger_matches(trigger: str, lower_query: str, tokens: set[str]) -> bool:
    if " " in trigger:
        return trigger in lower_query
    return trigger in tokens


def _trace_candidates(snippets: list[SourceSnippet], limit: int = 8) -> list[TraceCandidate]:
    return [
        TraceCandidate(
            chunk_id=snippet.chunk_id,
            section_number=snippet.section_number,
            section_title=snippet.section_title,
            source_type=snippet.source_type,
            score=snippet.score,
            text_preview=_preview(snippet.text),
        )
        for snippet in snippets[:limit]
    ]


def _preview(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}..."


def _intent_matches_key_clause(query: str, section_number: str) -> bool:
    lower = query.lower()
    if section_number == "1.3":
        return any(term in lower for term in ("secure", "security", "reasonable appropriate", "loss access disclosure"))
    if section_number == "5.1":
        return any(term in lower for term in ("term", "effective date", "commence", "remain in effect"))
    if section_number == "6.1":
        return any(term in lower for term in ("ownership", "obtain no rights", "licensors"))
    return False


def _asks_affirmative_obligation(query: str) -> bool:
    lower = query.lower()
    return any(
        term in lower
        for term in (
            "promise",
            "secure",
            "ownership",
            "obtain",
            "term",
            "commence",
            "responsible",
            "must",
            "notice",
        )
    )


def _asks_security(query: str) -> bool:
    lower = query.lower()
    return any(term in lower for term in ("secure", "security", "loss access disclosure", "reasonable appropriate measures"))


def _asks_ownership(query: str) -> bool:
    lower = query.lower()
    return any(term in lower for term in ("ownership", "obtain no rights", "licensors"))

"""Default implementation of the QueryService.

Orchestrates: query planning → evidence collection → prompt building → LLM answer → logging.
Does not know about ChromaDB, SQLite, or OpenAI — only interfaces.
"""

import json
import logging
import threading
import time
import typing
from dataclasses import replace

from assessment_app.services.query.public.models import QueryLogEntry, QueryTrace, SourceSnippet, TraceCandidate
from assessment_app.services.query.internal.evidence_collector import EvidenceCollector
from assessment_app.services.query.internal.ports import BaseChatModel, EvidenceVerifier, QueryLogger, SemanticStore
from assessment_app.services.query.internal.prompt_builder import NO_ANSWER_MESSAGE, answer_found, build_answer_messages
from assessment_app.services.query.internal.query_planner import QueryPlanner
from assessment_app.services.query.public.contracts import QueryService
from assessment_app.services.query.public.errors import NotIngestedError
from assessment_app.services.query.public.models import AskResult

logger = logging.getLogger(__name__)


class DefaultQueryService:
    """Orchestrates the full RAG query pipeline through interface contracts."""

    def __init__(
        self,
        semantic_store: SemanticStore,
        query_planner: QueryPlanner,
        evidence_collector: EvidenceCollector,
        evidence_verifier: EvidenceVerifier,
        chat_client: BaseChatModel,
        query_logger: QueryLogger,
    ) -> None:
        self._semantic_store = semantic_store
        self._query_planner = query_planner
        self._evidence_collector = evidence_collector
        self._evidence_verifier = evidence_verifier
        self._chat_client = chat_client
        self._query_logger = query_logger
        self._lock = threading.Lock()

    def ask(
        self,
        query: str,
        top_k: int | None = None,
        log_query: bool = True,
    ) -> typing.Iterable[dict[str, typing.Any]]:
        """Search the vector store, verify evidence, and generate a grounded answer."""
        with self._lock:
            started_at = time.perf_counter()
    
            if self._semantic_store.count() == 0:
                logger.warning("Query rejected: vector store is empty")
                raise NotIngestedError()
    
            logger.info("Stage 1: Planning query: %r", query)
            yield {"type": "progress", "stage": 0, "message": "Planning retrieval..."}
            plan = self._query_planner.plan(query)
            logger.info("Generated plan with %d sub-queries", len(plan.retrieval_queries))
            yield {"type": "progress", "stage": 0, "message": "Retrieval plan generated.", "data": {"plan": [q.__dict__ for q in plan.retrieval_queries]}}
            
            yield {"type": "progress", "stage": 1, "message": "Searching evidence..."}
            all_sources: dict[str, SourceSnippet] = {}
            trace_steps = []
            max_retries = 2
            
            for sub_query in plan.retrieval_queries:
                logger.info("Processing sub-query %s: %s", sub_query.query_id, sub_query.query)
                yield {"type": "progress", "stage": 1, "message": f"Searching evidence for: {sub_query.query}", "data": {"sub_query": sub_query.query}}
                current_snippets = self._evidence_collector.initial_search(sub_query, top_k, original_query=query)
                trace_step = self._evidence_collector.last_trace_step
                
                retries = 0
                last_verification = None
                expansion_actions: list[str] = []
                while retries <= max_retries:
                    if not current_snippets:
                        logger.warning("No evidence found for sub-query %s", sub_query.query_id)
                        break
                        
                    yield {"type": "progress", "stage": 2, "message": f"Verifying context for: {sub_query.query}"}
                    verification = self._evidence_verifier.verify(sub_query.query, current_snippets)
                    last_verification = verification
                    yield {"type": "progress", "stage": 2, "message": "Verification complete.", "data": {"verification": verification.__dict__}}
                    if getattr(verification, 'is_sufficient', True):
                        logger.info("Evidence sufficient for sub-query %s", sub_query.query_id)
                        break
                        
                    if retries < max_retries:
                        logger.info("Evidence insufficient for %s. Expanding context...", sub_query.query_id)
                        expanded_snippets = self._evidence_collector.expand_context(current_snippets, verification)
                        expansion_actions.extend(self._evidence_collector.last_expansion_actions)
                        
                        # Stop if expansion didn't add anything new
                        if len(expanded_snippets) <= len(current_snippets):
                            logger.info("Context expansion yielded no new chunks for %s", sub_query.query_id)
                            break
                            
                        current_snippets = expanded_snippets
                        retries += 1
                    else:
                        logger.warning("Max retries reached for sub-query %s", sub_query.query_id)
                        break
                
                for snippet in current_snippets:
                    if snippet.chunk_id not in all_sources:
                        all_sources[snippet.chunk_id] = snippet
                if trace_step:
                    trace_steps.append(
                        replace(
                            trace_step,
                            verifier=last_verification,
                            expansion_actions=sorted(set(expansion_actions)),
                        )
                    )

            sources = sorted(all_sources.values(), key=lambda s: getattr(s, 'order', 0))
            trace = QueryTrace(
                original_query=query,
                retrieval_steps=trace_steps,
                final_sources=_trace_candidates(sources),
            )
    
            if not sources:
                yield {"type": "complete", "result": self._package(query, NO_ANSWER_MESSAGE, False, [], started_at, log_query, trace)}
                return
    
            logger.info("Stage 4: Generating grounded answer from LLM...")
            yield {"type": "progress", "stage": 3, "message": "Answering with sources...", "data": {"sources_count": len(sources)}}
            result = self._chat_client.invoke(build_answer_messages(query, sources))
            answer = str(result.content).strip()
            found = answer_found(answer)
    
            logger.info("Stage 5: Query complete. found=%s latency_ms=%d", found, int((time.perf_counter() - started_at) * 1000))
    
            yield {"type": "complete", "result": self._package(query, answer, found, sources, started_at, log_query, trace)}

    def _package(self, query, answer, found, sources, started_at, log_query, trace=None):
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        if log_query:
            self._query_logger.log_query(
                QueryLogEntry(
                    query=query,
                    answer=answer,
                    answer_found=found,
                    latency_ms=latency_ms,
                    sources_json=json.dumps([source.__dict__ for source in sources]),
                )
            )
        return AskResult(answer=answer, answer_found=found, sources=sources, latency_ms=latency_ms, trace=trace)


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


# Runtime type check: DefaultQueryService must satisfy QueryService.
_: QueryService = DefaultQueryService.__new__(DefaultQueryService)  # type: ignore[assignment]

"""Default implementation of the QueryService.

Orchestrates: query planning → evidence collection → prompt building → LLM answer → logging.
Does not know about ChromaDB, SQLite, or OpenAI — only interfaces.
"""

import json
import logging
import threading
import time

from assessment_app.services.query.public.models import QueryLogEntry, SourceSnippet
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
    ) -> AskResult:
        """Search the vector store, verify evidence, and generate a grounded answer."""
        with self._lock:
            started_at = time.perf_counter()
    
            if self._semantic_store.count() == 0:
                logger.warning("Query rejected: vector store is empty")
                raise NotIngestedError()
    
            logger.info("Stage 1: Planning query: %r", query)
            plan = self._query_planner.plan(query)
            logger.info("Generated plan with %d sub-queries", len(plan.retrieval_queries))
            
            # Stage 2 & 3: Evidence collection and self-reflective verification loop
            all_sources: dict[str, SourceSnippet] = {}
            max_retries = 2
            
            for sub_query in plan.retrieval_queries:
                logger.info("Processing sub-query %s: %s", sub_query.query_id, sub_query.query)
                current_snippets = self._evidence_collector.initial_search(sub_query, top_k)
                
                retries = 0
                while retries <= max_retries:
                    if not current_snippets:
                        logger.warning("No evidence found for sub-query %s", sub_query.query_id)
                        break
                        
                    verification = self._evidence_verifier.verify(sub_query.query, current_snippets)
                    if getattr(verification, 'is_sufficient', True):
                        logger.info("Evidence sufficient for sub-query %s", sub_query.query_id)
                        break
                        
                    if retries < max_retries:
                        logger.info("Evidence insufficient for %s. Expanding context...", sub_query.query_id)
                        expanded_snippets = self._evidence_collector.expand_context(current_snippets, verification)
                        
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

            sources = sorted(all_sources.values(), key=lambda s: getattr(s, 'order', 0))
    
            if not sources:
                return self._package(query, NO_ANSWER_MESSAGE, False, [], started_at, log_query)
    
            logger.info("Stage 4: Generating grounded answer from LLM...")
            result = self._chat_client.invoke(build_answer_messages(query, sources))
            answer = str(result.content).strip()
            found = answer_found(answer)
    
            logger.info("Stage 5: Query complete. found=%s latency_ms=%d", found, int((time.perf_counter() - started_at) * 1000))
    
            return self._package(query, answer, found, sources, started_at, log_query)

    def _package(self, query, answer, found, sources, started_at, log_query):
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
        return AskResult(answer=answer, answer_found=found, sources=sources, latency_ms=latency_ms)


# Runtime type check: DefaultQueryService must satisfy QueryService.
_: QueryService = DefaultQueryService.__new__(DefaultQueryService)  # type: ignore[assignment]

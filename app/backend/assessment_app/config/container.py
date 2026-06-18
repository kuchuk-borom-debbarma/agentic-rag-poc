"""Composition root: builds the AppContainer by wiring concrete implementations.

This is the ONLY module allowed to import concrete infra classes.
Everything else depends on public service contracts.
"""

from dataclasses import dataclass

from assessment_app.config.settings import Settings

from assessment_app.infra.chroma.chroma_rag_vector_store import ChromaRagVectorStore
from assessment_app.infra.chroma.chroma_vector_store import ChromaVectorStore
from assessment_app.infra.documents.pdf_document_loader import PdfDocumentLoader
from assessment_app.infra.sqlite.sqlite_evaluation_repository import SqliteEvaluationRepository
from assessment_app.infra.sqlite.sqlite_graph_store import SqliteGraphStore
from assessment_app.infra.sqlite.sqlite_query_logger import SqliteQueryLogger
from assessment_app.services.analytics.internal.service_impl import DefaultAnalyticsService
from assessment_app.services.analytics.public.contracts import AnalyticsService
from assessment_app.services.evaluation.internal.benchmark_scorer import DefaultBenchmarkScorer
from assessment_app.services.evaluation.internal.service_impl import DefaultEvaluationService
from assessment_app.services.evaluation.public.contracts import EvaluationService
from assessment_app.services.query.internal.evidence_collector import EvidenceCollector
from assessment_app.services.query.internal.query_planner import QueryPlanner
from assessment_app.services.query.internal.service_impl import DefaultQueryService
from assessment_app.services.query.public.contracts import QueryService
from assessment_app.services.rag.internal.ingestion.graph_builder import GraphBuilder
from assessment_app.services.rag.internal.ingestion.parser import HierarchicalAwareParser
from assessment_app.services.rag.internal.ingestion.semantic_chunker import SemanticChunker
from assessment_app.services.rag.internal.ingestion.service_impl import (
    DefaultIngestionParsingService,
    DefaultSemanticChunkingService,
)
from assessment_app.services.rag.internal.service_impl import DefaultRagIngestionService
from assessment_app.services.rag.public.contracts import RagIngestionService


@dataclass(frozen=True)
class AppContainer:
    """Immutable container holding all wired service instances.

    Stored on app.state.container at startup.
    All fields are typed as contracts (Protocols), not concrete classes.
    """

    query_service: QueryService
    analytics_service: AnalyticsService
    evaluation_service: EvaluationService
    rag_ingestion_service: RagIngestionService


def build_container(settings: Settings) -> AppContainer:
    """Wire all concrete implementations and return a frozen AppContainer.

    This is the composition root. Only this function may import concrete classes.
    """
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    embedding_client = OpenAIEmbeddings(
        openai_api_base=settings.embedding_base_url,
        model=settings.embedding_model,
        openai_api_key=settings.embedding_api_key or "dummy",
        request_timeout=600,
        check_embedding_ctx_length=False,
    )
    chat_client = ChatOpenAI(
        openai_api_base=settings.chat_base_url,
        model=settings.chat_model,
        openai_api_key=settings.chat_api_key or "dummy",
        max_tokens=settings.chat_max_tokens,
        temperature=settings.chat_temperature,
        request_timeout=600,
    )

    vector_store = ChromaVectorStore(
        persist_dir=settings.chroma_dir,
        collection_name=settings.chroma_collection,
    )
    rag_vector_store = ChromaRagVectorStore(
        persist_dir=settings.chroma_dir,
        collection_name=settings.rag_chroma_collection,
        embedding_function=embedding_client,
    )
    query_logger = SqliteQueryLogger(sqlite_path=settings.sqlite_path)
    evaluation_repository = SqliteEvaluationRepository(sqlite_path=settings.sqlite_path)
    graph_store = SqliteGraphStore(sqlite_path=settings.graph_sqlite_path)



    # RAG ingestion service
    rag_ingestion_service: RagIngestionService = DefaultRagIngestionService(
        parsing_service=DefaultIngestionParsingService(
            document_loader=PdfDocumentLoader(pdf_path=settings.pdf_path),
            parser=HierarchicalAwareParser(),
        ),
        chunking_service=DefaultSemanticChunkingService(
            chunker=SemanticChunker(),
            embedding_client=embedding_client,
        ),
        graph_builder=GraphBuilder(),
        graph_store=graph_store,
        vector_store=rag_vector_store,
    )

    from assessment_app.services.query.internal.verifier import LLMEvidenceVerifier
    
    # Query service
    evidence_collector = EvidenceCollector(
        embedding_client=embedding_client,
        semantic_store=rag_vector_store,
        graph_store=graph_store,
        top_k=settings.default_top_k,
    )
    query_service: QueryService = DefaultQueryService(
        semantic_store=rag_vector_store,
        query_planner=QueryPlanner(chat_client=chat_client),
        evidence_collector=evidence_collector,
        evidence_verifier=LLMEvidenceVerifier(chat_client=chat_client),
        chat_client=chat_client,
        query_logger=query_logger,
    )

    # Analytics service
    analytics_service: AnalyticsService = DefaultAnalyticsService(
        analytics_reader=query_logger,
    )

    # Evaluation service
    evaluation_service: EvaluationService = DefaultEvaluationService(
        query_service=query_service,
        scorer=DefaultBenchmarkScorer(),
        run_repository=evaluation_repository,
        config_snapshot=(
            f"chat={settings.chat_model}; embedding={settings.embedding_model}; "
            f"top_k_default={settings.default_top_k}"
        ),
    )

    return AppContainer(
        query_service=query_service,
        analytics_service=analytics_service,
        evaluation_service=evaluation_service,
        rag_ingestion_service=rag_ingestion_service,
    )

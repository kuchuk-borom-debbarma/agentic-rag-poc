"""Unit tests for DefaultQueryService."""

from assessment_app.services.query.public.models import SourceSnippet
from assessment_app.services.query.internal.evidence_collector import EvidenceCollector
from assessment_app.services.query.internal.query_planner import QueryPlanner
from assessment_app.services.query.internal.service_impl import DefaultQueryService
from assessment_app.services.query.public.errors import NotIngestedError
from tests.fakes.fake_chat_client import FakeChatClient
from tests.fakes.fake_embedding_client import FakeEmbeddingClient
from tests.fakes.fake_query_logger import FakeQueryLogger
from tests.fakes.fake_vector_store import FakeEvidenceVerifier, FakeGraphStore, FakeSemanticStore
import pytest


def _source(chunk_id: str = "chunk_0001") -> SourceSnippet:
    return SourceSnippet(
        chunk_id=chunk_id,
        text="AWS may suspend services.",
        page_start=1,
        page_end=1,
        source_file="doc.pdf",
        section_id="section_1",
        section_number="1",
        section_title="Terms",
        parent_section_id=None,
        parent_section_number=None,
        parent_section_title=None,
        order=1,
        referenced_section_ids=[],
        source_type="semantic",
        score=None,
    )


def _build_service(snippets=None, chunk_count=1, chat_answer="Test answer."):
    snippets = snippets or [_source()]
    semantic_store = FakeSemanticStore(snippets=snippets, chunk_count=chunk_count)
    graph_store = FakeGraphStore(snippets=snippets)
    embedding_client = FakeEmbeddingClient()
    query_logger = FakeQueryLogger()
    evidence_verifier = FakeEvidenceVerifier(is_sufficient=True)

    evidence_collector = EvidenceCollector(
        embedding_client=embedding_client,
        semantic_store=semantic_store,
        graph_store=graph_store,
        top_k=5,
    )
    
    from unittest.mock import MagicMock
    
    chat_client = MagicMock()
    # Mock invoke() to return an AIMessage for stage 4
    from langchain_core.messages import AIMessage
    chat_client.invoke.return_value = AIMessage(content=chat_answer)
    
    planner_chat_client = MagicMock()
    # Mock with_structured_output to return a fake callable that returns our parsed schema
    from assessment_app.services.query.internal.query_planner import _QueryPlanSchema, _RetrievalQuerySchema
    planner_chat_client.with_structured_output.return_value = MagicMock(
        invoke=MagicMock(return_value=_QueryPlanSchema(
            retrieval_queries=[
                _RetrievalQuerySchema(
                    query_id="Q1", 
                    query="test", 
                    purpose="test", 
                    target_sections=[], 
                    include_references=False
                )
            ]
        ))
    )

    return DefaultQueryService(
        semantic_store=semantic_store,
        query_planner=QueryPlanner(chat_client=planner_chat_client),
        evidence_collector=evidence_collector,
        evidence_verifier=evidence_verifier,
        chat_client=chat_client,
        query_logger=query_logger,
    ), query_logger


def test_query_service_raises_not_ingested_when_empty():
    service, _ = _build_service(chunk_count=0)
    with pytest.raises(NotIngestedError):
        service.ask("What is section 1?")


def test_query_service_returns_answer_and_logs_query():
    service, logger = _build_service()

    result = service.ask("When may AWS suspend services?")

    assert result.answer_found is True
    assert len(result.sources) == 1
    assert len(logger.logged) == 1


def test_query_service_does_not_log_when_log_query_false():
    service, logger = _build_service()

    service.ask("What is section 1?", log_query=False)

    assert len(logger.logged) == 0

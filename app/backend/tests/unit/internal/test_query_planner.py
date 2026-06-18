"""Unit tests for QueryPlanner."""

from unittest.mock import MagicMock
from assessment_app.services.query.internal.query_planner import QueryPlanner, _QueryPlanSchema, _RetrievalQuerySchema

def test_query_planner_splits_multi_part_questions_and_targets_sections():
    chat_client = MagicMock()
    planner = QueryPlanner(chat_client=chat_client)
    planner._chain = MagicMock()
    planner._chain.invoke.return_value = _QueryPlanSchema(
        retrieval_queries=[
            _RetrievalQuerySchema(
                query_id="Q1",
                query="What does Section 2.1 say?",
                purpose="original",
                target_sections=["2.1"],
                include_references=False
            ),
            _RetrievalQuerySchema(
                query_id="Q2",
                query="how does it affect Section 1.1?",
                purpose="branch",
                target_sections=["1.1"],
                include_references=True
            )
        ]
    )
    
    plan = planner.plan("What does Section 2.1 say and how does it affect Section 1.1?")
    
    assert len(plan.retrieval_queries) == 2
    
    q1 = plan.retrieval_queries[0]
    assert q1.query_id == "Q1"
    assert q1.target_sections == ["2.1"]
    
    q2 = plan.retrieval_queries[1]
    assert q2.query_id == "Q2"
    assert q2.target_sections == ["1.1"]
    assert q2.include_references is True


def test_query_planner_short_query_produces_exactly_one_retrieval():
    chat_client = MagicMock()
    planner = QueryPlanner(chat_client=chat_client)
    planner._chain = MagicMock()
    planner._chain.invoke.return_value = _QueryPlanSchema(
        retrieval_queries=[
            _RetrievalQuerySchema(
                query_id="Q1",
                query="What is the effective date?",
                purpose="original",
                target_sections=[],
                include_references=False
            )
        ]
    )
    
    plan = planner.plan("What is the effective date?")
    
    assert len(plan.retrieval_queries) == 1
    assert plan.retrieval_queries[0].query == "What is the effective date?"
    assert plan.retrieval_queries[0].target_sections == []

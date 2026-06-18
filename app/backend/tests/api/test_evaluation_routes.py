"""API tests for benchmark evaluation routes."""

from fastapi.testclient import TestClient

from assessment_app.config.dependencies import get_evaluation_service
from assessment_app.main import create_app
from assessment_app.services.evaluation.public.models import (
    BenchmarkCase,
    EvaluationCaseResult,
    EvaluationCategory,
    EvaluationMetric,
    EvaluationRunDetail,
    EvaluationRunSummary,
)
from assessment_app.services.query.public.models import SourceSnippet


def test_evaluation_routes_run_list_and_load_detail():
    service = _FakeEvaluationService()
    app = create_app()
    app.dependency_overrides[get_evaluation_service] = lambda: service

    with TestClient(app) as client:
        run_response = client.post("/api/v1/evaluation/runs", json={"top_k": 5})
        list_response = client.get("/api/v1/evaluation/runs")
        detail_response = client.get("/api/v1/evaluation/runs/eval_test")
        old_response = client.post("/api/v1/evaluation/query", json={"query": "old"})

    assert run_response.status_code == 200
    assert run_response.json()["summary"]["run_id"] == "eval_test"
    assert service.last_top_k == 5
    assert list_response.status_code == 200
    assert list_response.json()[0]["overall_score"] == 0.9
    assert detail_response.status_code == 200
    assert detail_response.json()["cases"][0]["case"]["id"] == "case_1"
    assert old_response.status_code == 404


class _FakeEvaluationService:
    def __init__(self) -> None:
        self.last_top_k: int | None = None
        self.detail = _detail()

    def run_benchmark(self, top_k=None, case_ids=None):
        self.last_top_k = top_k
        return self.detail

    def list_runs(self, limit=20):
        return [self.detail.summary]

    def get_run(self, run_id: str):
        return self.detail


def _detail() -> EvaluationRunDetail:
    category = EvaluationCategory(
        key="retrieval",
        label="Retrieval Quality",
        score=0.9,
        status="good",
        metrics=[
            EvaluationMetric(
                key="section_recall",
                label="Section Recall",
                category="retrieval",
                score=1.0,
                value="1/1 sections",
                status="good",
                details="Expected sections found.",
            )
        ],
    )
    return EvaluationRunDetail(
        summary=EvaluationRunSummary(
            run_id="eval_test",
            created_at="2026-06-18T00:00:00+00:00",
            top_k=5,
            case_count=1,
            overall_score=0.9,
            retrieval_score=0.9,
            answer_score=0.9,
            system_score=0.9,
            pass_rate=1.0,
            average_latency_ms=25.0,
            p95_latency_ms=25,
            total_latency_ms=30,
            config_snapshot="chat=test",
        ),
        categories=[category],
        cases=[
            EvaluationCaseResult(
                case=BenchmarkCase(
                    id="case_1",
                    query="What notice does AWS provide?",
                    expected_answer="AWS provides notice.",
                    expected_section_numbers=["1.5"],
                    answer_type="answerable",
                    tags=["notice"],
                ),
                answer="AWS provides notice.",
                answer_found=True,
                expected_section_numbers=["1.5"],
                retrieved_section_numbers=["1.5"],
                latency_ms=25,
                passed=True,
                categories=[category],
                sources=[_source()],
            )
        ],
    )


def _source() -> SourceSnippet:
    return SourceSnippet(
        chunk_id="section_1_5:0:0",
        text="AWS provides notice.",
        page_start=1,
        page_end=1,
        source_file="doc.pdf",
        section_id="section_1_5",
        section_number="1.5",
        section_title="Notice",
        parent_section_id="section_1",
        parent_section_number="1",
        parent_section_title="AWS Responsibilities",
        order=1,
        referenced_section_ids=[],
        source_type="semantic",
        score=None,
    )

"""Integration tests for SQLite evaluation history repository."""

from assessment_app.infra.sqlite.sqlite_evaluation_repository import SqliteEvaluationRepository
from assessment_app.services.evaluation.public.models import (
    BenchmarkCase,
    EvaluationCaseResult,
    EvaluationCategory,
    EvaluationMetric,
    EvaluationRunDetail,
    EvaluationRunSummary,
)
from assessment_app.services.query.public.models import SourceSnippet


def test_sqlite_evaluation_repository_round_trips_run_detail(tmp_path):
    repository = SqliteEvaluationRepository(tmp_path / "usage.db")
    detail = _detail()

    repository.save_run(detail)

    summaries = repository.list_runs(limit=10)
    loaded = repository.get_run("eval_test")

    assert [summary.run_id for summary in summaries] == ["eval_test"]
    assert loaded is not None
    assert loaded.summary.overall_score == 0.9
    assert loaded.summary.config_snapshot == "chat=test"
    assert loaded.categories[0].key == "retrieval"
    assert loaded.cases[0].case.id == "case_1"
    assert loaded.cases[0].sources[0].section_number == "1.5"


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

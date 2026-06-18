"""Unit tests for DefaultEvaluationService."""

from assessment_app.services.evaluation.internal.benchmark_scorer import DefaultBenchmarkScorer
from assessment_app.services.evaluation.internal.service_impl import DefaultEvaluationService
from assessment_app.services.evaluation.public.errors import BenchmarkCaseNotFoundError
from assessment_app.services.evaluation.public.models import EvaluationRunDetail
from assessment_app.services.query.public.models import AskResult, SourceSnippet


class FakeQueryService:
    """Captures benchmark query calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None, bool]] = []

    def ask(self, query: str, top_k=None, log_query=True) -> AskResult:
        self.calls.append((query, top_k, log_query))
        return AskResult(
            answer="AWS provides at least 12 months prior notice before discontinuing material functionality.",
            answer_found=True,
            sources=[_source("section_1_5:0:0", "1.5")],
            latency_ms=25,
        )


class FakeRunRepository:
    def __init__(self) -> None:
        self.saved: EvaluationRunDetail | None = None

    def save_run(self, detail: EvaluationRunDetail) -> None:
        self.saved = detail

    def list_runs(self, limit: int):
        return [self.saved.summary] if self.saved else []

    def get_run(self, run_id: str):
        if self.saved and self.saved.summary.run_id == run_id:
            return self.saved
        return None


def test_evaluation_service_runs_benchmark_without_logging_and_persists_result():
    query_service = FakeQueryService()
    repository = FakeRunRepository()
    service = DefaultEvaluationService(
        query_service=query_service,
        scorer=DefaultBenchmarkScorer(),
        run_repository=repository,
        config_snapshot="chat=test; embedding=test; top_k_default=5",
    )

    result = service.run_benchmark(top_k=5, case_ids=["aws-003"])

    assert query_service.calls == [(result.cases[0].case.query, 5, False)]
    assert repository.saved == result
    assert result.summary.case_count == 1
    assert result.summary.retrieval_score > 0
    assert result.summary.answer_score > 0
    assert len(result.categories) == 3


def test_evaluation_service_rejects_unknown_case_id():
    service = DefaultEvaluationService(
        query_service=FakeQueryService(),
        scorer=DefaultBenchmarkScorer(),
        run_repository=FakeRunRepository(),
        config_snapshot="test",
    )

    try:
        service.run_benchmark(case_ids=["missing-case"])
    except BenchmarkCaseNotFoundError as exc:
        assert exc.case_id == "missing-case"
    else:
        raise AssertionError("Expected BenchmarkCaseNotFoundError")


def _source(chunk_id: str, section_number: str) -> SourceSnippet:
    return SourceSnippet(
        chunk_id=chunk_id,
        text="AWS provides at least 12 months prior notice before discontinuing material functionality.",
        page_start=1,
        page_end=1,
        source_file="doc.pdf",
        section_id=f"section_{section_number.replace('.', '_')}",
        section_number=section_number,
        section_title="Notice of Changes to the Services",
        parent_section_id="section_1",
        parent_section_number="1",
        parent_section_title="AWS Responsibilities",
        order=1,
        referenced_section_ids=[],
        source_type="semantic",
        score=None,
    )

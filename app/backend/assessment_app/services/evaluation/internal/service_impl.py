"""Default implementation of the EvaluationService."""

from datetime import UTC, datetime
import time
from uuid import uuid4

from assessment_app.services.evaluation.internal.benchmark_cases import get_benchmark_cases
from assessment_app.services.evaluation.internal.ports import BenchmarkScorer, EvaluationRunRepository
from assessment_app.services.evaluation.public.contracts import EvaluationService
from assessment_app.services.evaluation.public.errors import BenchmarkCaseNotFoundError, EvaluationRunNotFoundError
from assessment_app.services.evaluation.public.models import BenchmarkCase, EvaluationRunDetail, EvaluationRunSummary
from assessment_app.services.query.public.contracts import QueryService


class DefaultEvaluationService:
    """Runs benchmark cases without logging and persists evaluation history."""

    def __init__(
        self,
        query_service: QueryService,
        scorer: BenchmarkScorer,
        run_repository: EvaluationRunRepository,
        config_snapshot: str,
    ) -> None:
        self._query_service = query_service
        self._scorer = scorer
        self._run_repository = run_repository
        self._config_snapshot = config_snapshot

    def run_benchmark(self, top_k: int | None = None, case_ids: list[str] | None = None) -> EvaluationRunDetail:
        """Run selected benchmark cases through the real query service."""
        selected_cases = self._select_cases(case_ids)
        run_id = f"eval_{uuid4().hex}"
        created_at = datetime.now(UTC).isoformat()
        started_at = time.perf_counter()

        case_results = []
        for benchmark_case in selected_cases:
            query_result = self._query_service.ask(benchmark_case.query, top_k, log_query=False)
            case_results.append(self._scorer.score_case(benchmark_case, query_result))

        total_latency_ms = int((time.perf_counter() - started_at) * 1000)
        summary = self._scorer.summarize_run(
            run_id=run_id,
            created_at=created_at,
            top_k=top_k,
            case_results=case_results,
            total_latency_ms=total_latency_ms,
            config_snapshot=self._config_snapshot,
        )
        detail = EvaluationRunDetail(
            summary=summary,
            categories=self._scorer.summarize_categories(summary, case_results),
            cases=case_results,
        )
        self._run_repository.save_run(detail)
        return detail

    def list_runs(self, limit: int = 20) -> list[EvaluationRunSummary]:
        """Return stored evaluation run summaries, newest first."""
        return self._run_repository.list_runs(limit)

    def get_run(self, run_id: str) -> EvaluationRunDetail:
        """Return a stored run detail by id."""
        detail = self._run_repository.get_run(run_id)
        if detail is None:
            raise EvaluationRunNotFoundError(run_id)
        return detail

    def _select_cases(self, case_ids: list[str] | None) -> list[BenchmarkCase]:
        cases = get_benchmark_cases()
        if not case_ids:
            return cases

        by_id = {benchmark_case.id: benchmark_case for benchmark_case in cases}
        selected: list[BenchmarkCase] = []
        for case_id in case_ids:
            benchmark_case = by_id.get(case_id)
            if benchmark_case is None:
                raise BenchmarkCaseNotFoundError(case_id)
            selected.append(benchmark_case)
        return selected


_: EvaluationService = DefaultEvaluationService.__new__(DefaultEvaluationService)  # type: ignore[assignment]

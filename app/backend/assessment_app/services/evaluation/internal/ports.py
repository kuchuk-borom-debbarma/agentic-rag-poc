"""Internal port definitions owned by the evaluation service.

Infra adapters or concrete implementations satisfy these protocols.
Other services must NOT import from this module.
"""

from typing import Protocol

from assessment_app.services.evaluation.public.models import (
    BenchmarkCase,
    EvaluationCategory,
    EvaluationCaseResult,
    EvaluationRunDetail,
    EvaluationRunSummary,
)
from assessment_app.services.query.public.models import AskResult


class BenchmarkScorer(Protocol):
    """Score benchmark cases and aggregate run-level metrics."""

    def score_case(self, case: BenchmarkCase, result: AskResult) -> EvaluationCaseResult:
        """Score one query result against its golden benchmark case."""
        ...

    def summarize_run(
        self,
        run_id: str,
        created_at: str,
        top_k: int | None,
        case_results: list[EvaluationCaseResult],
        total_latency_ms: int,
        config_snapshot: str,
    ) -> EvaluationRunSummary:
        """Build the persisted run summary from per-case results."""
        ...

    def summarize_categories(
        self,
        summary: EvaluationRunSummary,
        case_results: list[EvaluationCaseResult],
    ) -> list[EvaluationCategory]:
        """Build run-level category metrics from a summary and its case results."""
        ...


class EvaluationRunRepository(Protocol):
    """Persist and load benchmark evaluation runs."""

    def save_run(self, detail: EvaluationRunDetail) -> None:
        """Store a run summary and all per-case results."""
        ...

    def list_runs(self, limit: int) -> list[EvaluationRunSummary]:
        """Return stored run summaries, newest first."""
        ...

    def get_run(self, run_id: str) -> EvaluationRunDetail | None:
        """Return one stored run with case details, or None."""
        ...

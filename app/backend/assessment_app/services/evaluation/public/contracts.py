"""Public contract for the evaluation bounded context.

Only this file (and models.py / errors.py) may be imported by routes, other services, or config.
"""

import typing
from typing import Protocol

from assessment_app.services.evaluation.public.models import EvaluationRunDetail, EvaluationRunSummary


class EvaluationService(Protocol):
    """Public contract for benchmark evaluation."""

    def run_benchmark(self, top_k: int | None = None, case_ids: list[str] | None = None) -> typing.Iterable[dict[str, typing.Any]]:
        """Run selected benchmark cases through the real query flow without analytics logging."""
        ...

    def list_runs(self, limit: int = 20) -> list[EvaluationRunSummary]:
        """Return stored evaluation run summaries, newest first."""
        ...

    def get_run(self, run_id: str) -> EvaluationRunDetail:
        """Return one stored evaluation run with per-case details."""
        ...

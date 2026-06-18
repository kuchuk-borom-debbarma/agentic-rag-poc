"""Public errors for the evaluation bounded context."""


class EvaluationError(Exception):
    """Base error for the evaluation service."""


class EvaluationRunNotFoundError(EvaluationError):
    """Raised when an evaluation run id does not exist."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"Evaluation run not found: {run_id}")


class BenchmarkCaseNotFoundError(EvaluationError):
    """Raised when a requested benchmark case id does not exist."""

    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        super().__init__(f"Benchmark case not found: {case_id}")

"""Public models for the evaluation bounded context."""

from dataclasses import dataclass

from assessment_app.services.query.public.models import QueryTrace, SourceSnippet


@dataclass(frozen=True)
class BenchmarkCase:
    """One golden question used by benchmark evaluation."""

    id: str
    query: str
    expected_answer: str
    expected_section_numbers: list[str]
    answer_type: str
    tags: list[str]


@dataclass(frozen=True)
class EvaluationMetric:
    """A single scored metric within a category."""

    key: str
    label: str
    category: str
    score: float
    value: str
    status: str
    details: str


@dataclass(frozen=True)
class EvaluationCategory:
    """A named group of related metrics with an aggregate score."""

    key: str
    label: str
    score: float
    status: str
    metrics: list[EvaluationMetric]


@dataclass(frozen=True)
class EvaluationCaseResult:
    """Evaluation output for one benchmark case."""

    case: BenchmarkCase
    answer: str
    answer_found: bool
    expected_section_numbers: list[str]
    retrieved_section_numbers: list[str]
    latency_ms: int
    passed: bool
    categories: list[EvaluationCategory]
    sources: list[SourceSnippet]
    trace: QueryTrace | None = None


@dataclass(frozen=True)
class EvaluationRunSummary:
    """Stored summary for one benchmark run."""

    run_id: str
    created_at: str
    top_k: int | None
    case_count: int
    overall_score: float
    retrieval_score: float
    answer_score: float
    system_score: float
    pass_rate: float
    average_latency_ms: float
    p95_latency_ms: int
    total_latency_ms: int
    config_snapshot: str


@dataclass(frozen=True)
class EvaluationRunDetail:
    """Full stored result for one benchmark run."""

    summary: EvaluationRunSummary
    categories: list[EvaluationCategory]
    cases: list[EvaluationCaseResult]

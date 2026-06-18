"""Benchmark evaluation routes."""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from assessment_app.config.dependencies import EvaluationServiceDep
from assessment_app.routes.dtos import SourceResponse
from assessment_app.services.evaluation.public.models import (
    BenchmarkCase,
    EvaluationCaseResult,
    EvaluationCategory,
    EvaluationRunDetail,
    EvaluationRunSummary,
)

router = APIRouter()


class RunBenchmarkRequest(BaseModel):
    top_k: int | None = Field(default=None, ge=1, le=20)
    case_ids: list[str] | None = None


class BenchmarkCaseResponse(BaseModel):
    id: str
    query: str
    expected_answer: str
    expected_section_numbers: list[str]
    answer_type: str
    tags: list[str]


class EvaluationMetricResponse(BaseModel):
    key: str
    label: str
    category: str
    score: float
    value: str
    status: str
    details: str


class EvaluationCategoryResponse(BaseModel):
    key: str
    label: str
    score: float
    status: str
    metrics: list[EvaluationMetricResponse]


class EvaluationCaseResultResponse(BaseModel):
    case: BenchmarkCaseResponse
    answer: str
    answer_found: bool
    expected_section_numbers: list[str]
    retrieved_section_numbers: list[str]
    latency_ms: int
    passed: bool
    categories: list[EvaluationCategoryResponse]
    sources: list[SourceResponse]


class EvaluationRunSummaryResponse(BaseModel):
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


class EvaluationRunDetailResponse(BaseModel):
    summary: EvaluationRunSummaryResponse
    categories: list[EvaluationCategoryResponse]
    cases: list[EvaluationCaseResultResponse]


@router.post("/runs", response_model=EvaluationRunDetailResponse)
async def run_evaluation(request: RunBenchmarkRequest, service: EvaluationServiceDep) -> EvaluationRunDetailResponse:
    """Run benchmark evaluation and persist the result."""
    return _detail_response(service.run_benchmark(top_k=request.top_k, case_ids=request.case_ids))


@router.get("/runs", response_model=list[EvaluationRunSummaryResponse])
async def list_evaluation_runs(
    service: EvaluationServiceDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[EvaluationRunSummaryResponse]:
    """List previous benchmark evaluation runs."""
    return [_summary_response(summary) for summary in service.list_runs(limit)]


@router.get("/runs/{run_id}", response_model=EvaluationRunDetailResponse)
async def get_evaluation_run(run_id: str, service: EvaluationServiceDep) -> EvaluationRunDetailResponse:
    """Load a previous benchmark evaluation run."""
    return _detail_response(service.get_run(run_id))


def _detail_response(detail: EvaluationRunDetail) -> EvaluationRunDetailResponse:
    return EvaluationRunDetailResponse(
        summary=_summary_response(detail.summary),
        categories=[_category_response(category) for category in detail.categories],
        cases=[_case_result_response(case_result) for case_result in detail.cases],
    )


def _summary_response(summary: EvaluationRunSummary) -> EvaluationRunSummaryResponse:
    return EvaluationRunSummaryResponse(**summary.__dict__)


def _case_result_response(case_result: EvaluationCaseResult) -> EvaluationCaseResultResponse:
    return EvaluationCaseResultResponse(
        case=_case_response(case_result.case),
        answer=case_result.answer,
        answer_found=case_result.answer_found,
        expected_section_numbers=case_result.expected_section_numbers,
        retrieved_section_numbers=case_result.retrieved_section_numbers,
        latency_ms=case_result.latency_ms,
        passed=case_result.passed,
        categories=[_category_response(category) for category in case_result.categories],
        sources=[SourceResponse(**source.__dict__) for source in case_result.sources],
    )


def _case_response(case: BenchmarkCase) -> BenchmarkCaseResponse:
    return BenchmarkCaseResponse(**case.__dict__)


def _category_response(category: EvaluationCategory) -> EvaluationCategoryResponse:
    return EvaluationCategoryResponse(
        key=category.key,
        label=category.label,
        score=category.score,
        status=category.status,
        metrics=[EvaluationMetricResponse(**metric.__dict__) for metric in category.metrics],
    )

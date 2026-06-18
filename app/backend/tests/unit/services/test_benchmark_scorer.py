"""Unit tests for DefaultBenchmarkScorer."""

from assessment_app.services.evaluation.internal.benchmark_scorer import DefaultBenchmarkScorer
from assessment_app.services.evaluation.public.models import BenchmarkCase
from assessment_app.services.query.public.models import AskResult, SourceSnippet


def test_scorer_rewards_full_expected_section_retrieval():
    case = _case(expected_sections=["1.5", "1.6"])
    result = AskResult(
        answer="AWS gives 12 months notice for material functionality and 90 days for adverse SLA changes.",
        answer_found=True,
        sources=[_source("chunk_1", "1.5"), _source("chunk_2", "1.6")],
        latency_ms=100,
    )

    scored = DefaultBenchmarkScorer().score_case(case, result)
    retrieval = _category(scored, "retrieval")

    metrics = {metric.key: metric for metric in retrieval.metrics}
    assert metrics["section_recall"].score == 1.0
    assert metrics["section_precision"].score == 1.0
    assert scored.passed is True


def test_scorer_flags_partial_and_missing_retrieval():
    case = _case(expected_sections=["1.5", "1.6"])
    partial = AskResult(
        answer="AWS gives notice for changes.",
        answer_found=True,
        sources=[_source("chunk_1", "1.5"), _source("chunk_9", "3.1")],
        latency_ms=100,
    )
    missing = AskResult(answer="No answer.", answer_found=False, sources=[], latency_ms=100)

    scorer = DefaultBenchmarkScorer()
    partial_metrics = {metric.key: metric for metric in _category(scorer.score_case(case, partial), "retrieval").metrics}
    missing_metrics = {metric.key: metric for metric in _category(scorer.score_case(case, missing), "retrieval").metrics}

    assert partial_metrics["section_recall"].score == 0.5
    assert partial_metrics["section_precision"].score == 0.5
    assert missing_metrics["section_recall"].score == 0.0
    assert missing_metrics["evidence_found"].score == 0.0


def test_scorer_handles_unanswerable_cases():
    case = BenchmarkCase(
        id="case_unanswerable",
        query="What universal uptime does AWS guarantee?",
        expected_answer="The agreement does not state one universal uptime percentage.",
        expected_section_numbers=["1.1", "1.6"],
        answer_type="unanswerable",
        tags=["unanswerable"],
    )
    refused = AskResult(
        answer="I could not find this in the provided agreement.",
        answer_found=False,
        sources=[_source("chunk_1", "1.1"), _source("chunk_2", "1.6")],
        latency_ms=100,
    )
    hallucinated = AskResult(
        answer="AWS guarantees 99.99% uptime for every service.",
        answer_found=True,
        sources=[_source("chunk_1", "1.1")],
        latency_ms=100,
    )

    scorer = DefaultBenchmarkScorer()
    refused_answer = {metric.key: metric for metric in _category(scorer.score_case(case, refused), "answer").metrics}
    hallucinated_answer = {metric.key: metric for metric in _category(scorer.score_case(case, hallucinated), "answer").metrics}

    assert refused_answer["answer_found_accuracy"].score == 1.0
    assert refused_answer["unsupported_answer_penalty"].score == 1.0
    assert hallucinated_answer["answer_found_accuracy"].score == 0.0
    assert hallucinated_answer["unsupported_answer_penalty"].score == 0.0


def _case(expected_sections: list[str]) -> BenchmarkCase:
    return BenchmarkCase(
        id="case_notice",
        query="What notice does AWS provide for service and SLA changes?",
        expected_answer="AWS gives 12 months notice for material service functionality discontinuation and 90 days notice for adverse SLA changes.",
        expected_section_numbers=expected_sections,
        answer_type="answerable",
        tags=["notice"],
    )


def _source(chunk_id: str, section_number: str) -> SourceSnippet:
    return SourceSnippet(
        chunk_id=chunk_id,
        text="AWS gives notice before discontinuing material functionality or making adverse SLA changes.",
        page_start=1,
        page_end=1,
        source_file="doc.pdf",
        section_id=f"section_{section_number.replace('.', '_')}",
        section_number=section_number,
        section_title="Notice",
        parent_section_id=None,
        parent_section_number=None,
        parent_section_title=None,
        order=1,
        referenced_section_ids=[],
        source_type="semantic",
        score=None,
    )


def _category(result, key):
    return next(category for category in result.categories if category.key == key)

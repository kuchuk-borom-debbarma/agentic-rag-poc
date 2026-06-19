"""Deterministic benchmark scoring for RAG evaluation."""

import math
import re

from assessment_app.services.evaluation.public.models import (
    BenchmarkCase,
    EvaluationCategory,
    EvaluationCaseResult,
    EvaluationMetric,
    EvaluationRunSummary,
)
from assessment_app.services.query.public.models import AskResult, SourceSnippet


STOP_WORDS = frozenset(
    [
        "a", "an", "and", "are", "as", "at", "be", "by", "for",
        "from", "has", "have", "if", "in", "is", "it", "of", "on",
        "or", "that", "the", "this", "to", "was", "we", "with",
        "you", "your", "any", "all", "will", "may",
    ]
)


class DefaultBenchmarkScorer:
    """Score benchmark cases against deterministic golden expectations."""

    def score_case(self, case: BenchmarkCase, result: AskResult) -> EvaluationCaseResult:
        retrieved_sections = _unique_sections(result.sources)
        retrieval = self._retrieval_category(case, result.sources, retrieved_sections)
        answer = self._answer_category(case, result, retrieved_sections)
        system = self._system_category(result)
        categories = [retrieval, answer, system]
        passed = retrieval.score >= 0.5 and answer.score >= 0.6 and system.score >= 0.5

        return EvaluationCaseResult(
            case=case,
            answer=result.answer,
            answer_found=result.answer_found,
            expected_section_numbers=case.expected_section_numbers,
            retrieved_section_numbers=retrieved_sections,
            latency_ms=result.latency_ms,
            passed=passed,
            categories=categories,
            sources=result.sources,
            trace=result.trace,
        )

    def summarize_run(
        self,
        run_id: str,
        created_at: str,
        top_k: int | None,
        case_results: list[EvaluationCaseResult],
        total_latency_ms: int,
        config_snapshot: str,
    ) -> EvaluationRunSummary:
        retrieval_score = _average(_category_scores(case_results, "retrieval"))
        answer_score = _average(_category_scores(case_results, "answer"))
        system_score = _average(_category_scores(case_results, "system"))
        overall_score = _average([retrieval_score, answer_score, system_score])
        latencies = [case.latency_ms for case in case_results]

        return EvaluationRunSummary(
            run_id=run_id,
            created_at=created_at,
            top_k=top_k,
            case_count=len(case_results),
            overall_score=round(overall_score, 3),
            retrieval_score=round(retrieval_score, 3),
            answer_score=round(answer_score, 3),
            system_score=round(system_score, 3),
            pass_rate=round(_average([1.0 if case.passed else 0.0 for case in case_results]), 3),
            average_latency_ms=round(_average([float(value) for value in latencies]), 1),
            p95_latency_ms=_p95(latencies),
            total_latency_ms=total_latency_ms,
            config_snapshot=config_snapshot,
        )

    def summarize_categories(
        self,
        summary: EvaluationRunSummary,
        case_results: list[EvaluationCaseResult],
    ) -> list[EvaluationCategory]:
        average_context_chars = _average([float(_context_chars(case.sources)) for case in case_results])
        return [
            _category(
                "retrieval",
                "Retrieval Quality",
                [
                    _metric(
                        "retrieval_score",
                        "Retrieval Score",
                        "retrieval",
                        summary.retrieval_score,
                        _percent(summary.retrieval_score),
                        "Average of section recall, section precision, evidence found, source count, and dedupe rate.",
                    ),
                    _metric(
                        "case_pass_rate",
                        "Case Pass Rate",
                        "retrieval",
                        summary.pass_rate,
                        _percent(summary.pass_rate),
                        "Share of benchmark cases that met category thresholds.",
                    ),
                ],
            ),
            _category(
                "answer",
                "Answer Quality",
                [
                    _metric(
                        "answer_score",
                        "Answer Score",
                        "answer",
                        summary.answer_score,
                        _percent(summary.answer_score),
                        "Average expected-answer overlap, answer-found accuracy, citation accuracy, and unsupported-answer checks.",
                    ),
                    _metric(
                        "unsupported_answer_safety",
                        "Unsupported Answer Safety",
                        "answer",
                        _average(_metric_scores(case_results, "answer", "unsupported_answer_penalty")),
                        _percent(_average(_metric_scores(case_results, "answer", "unsupported_answer_penalty"))),
                        "Penalizes answers for unanswerable cases and missing answers for answerable cases.",
                    ),
                ],
            ),
            _category(
                "system",
                "System Quality",
                [
                    _metric(
                        "system_score",
                        "System Score",
                        "system",
                        summary.system_score,
                        _percent(summary.system_score),
                        "Average latency and context-volume efficiency.",
                    ),
                    _metric(
                        "average_latency",
                        "Average Latency",
                        "system",
                        _latency_score(int(summary.average_latency_ms), good_ms=2_000, warn_ms=8_000),
                        f"{summary.average_latency_ms} ms",
                        "Average real query-flow latency across benchmark cases.",
                    ),
                    _metric(
                        "p95_latency",
                        "P95 Latency",
                        "system",
                        _latency_score(summary.p95_latency_ms, good_ms=4_000, warn_ms=12_000),
                        f"{summary.p95_latency_ms} ms",
                        "Approximate p95 latency across benchmark cases.",
                    ),
                    _metric(
                        "context_volume",
                        "Context Volume",
                        "system",
                        _volume_score(int(average_context_chars)),
                        f"{int(average_context_chars)} avg chars",
                        "Average retrieved evidence text volume sent toward answer generation.",
                    ),
                ],
            ),
        ]

    def _retrieval_category(
        self,
        case: BenchmarkCase,
        sources: list[SourceSnippet],
        retrieved_sections: list[str],
    ) -> EvaluationCategory:
        expected = set(case.expected_section_numbers)
        retrieved = set(retrieved_sections)
        overlap = expected & retrieved
        source_count = len(sources)
        unique_chunks = len({source.chunk_id for source in sources})

        return _category(
            "retrieval",
            "Retrieval Quality",
            [
                _metric(
                    "section_recall",
                    "Section Recall",
                    "retrieval",
                    len(overlap) / len(expected) if expected else 1.0,
                    f"{len(overlap)}/{len(expected)} sections",
                    "Expected source sections found in retrieved evidence.",
                ),
                _metric(
                    "section_precision",
                    "Section Precision",
                    "retrieval",
                    len(overlap) / len(retrieved) if retrieved else 0.0,
                    f"{len(overlap)}/{len(retrieved)} retrieved",
                    "Retrieved sections that match the golden evidence sections.",
                ),
                _metric(
                    "evidence_found",
                    "Evidence Found",
                    "retrieval",
                    1.0 if source_count else 0.0,
                    f"{source_count} sources",
                    "Checks whether the query returned any evidence.",
                ),
                _metric(
                    "source_count",
                    "Source Count",
                    "retrieval",
                    _source_count_score(source_count),
                    f"{source_count} sources",
                    "Rewards enough evidence without flooding the answer context.",
                ),
                _metric(
                    "dedupe_rate",
                    "Dedupe Rate",
                    "retrieval",
                    unique_chunks / source_count if source_count else 0.0,
                    f"{unique_chunks}/{source_count} unique",
                    "Duplicate chunks waste context and can bias answers.",
                ),
            ],
        )

    def _answer_category(
        self,
        case: BenchmarkCase,
        result: AskResult,
        retrieved_sections: list[str],
    ) -> EvaluationCategory:
        answerable = case.answer_type == "answerable"
        expected = set(case.expected_section_numbers)
        retrieved = set(retrieved_sections)
        expected_overlap = _answer_overlap(case.expected_answer, result.answer)
        if not answerable and not result.answer_found:
            expected_overlap = 1.0

        answer_found_accuracy = 1.0 if result.answer_found == answerable else 0.0
        unsupported_score = 1.0
        if answerable and not result.answer_found:
            unsupported_score = 0.0
        if not answerable and result.answer_found:
            unsupported_score = 0.0

        return _category(
            "answer",
            "Answer Quality",
            [
                _metric(
                    "expected_answer_overlap",
                    "Expected Answer Overlap",
                    "answer",
                    expected_overlap,
                    _percent(expected_overlap),
                    "Lexical overlap between actual answer and the golden answer.",
                ),
                _metric(
                    "answer_found_accuracy",
                    "Answer Found Accuracy",
                    "answer",
                    answer_found_accuracy,
                    "correct" if answer_found_accuracy == 1.0 else "wrong",
                    "Checks answerable cases are answered and unanswerable cases are refused.",
                ),
                _metric(
                    "citation_section_accuracy",
                    "Citation Section Accuracy",
                    "answer",
                    len(expected & retrieved) / len(expected) if expected else 1.0,
                    f"{len(expected & retrieved)}/{len(expected)} sections",
                    "Checks whether cited evidence includes the sections needed by the answer.",
                ),
                _metric(
                    "unsupported_answer_penalty",
                    "Unsupported Answer Check",
                    "answer",
                    unsupported_score,
                    "pass" if unsupported_score == 1.0 else "fail",
                    "Penalizes unsupported answers and missed answerable questions.",
                ),
            ],
        )

    def _system_category(self, result: AskResult) -> EvaluationCategory:
        evidence_chars = _context_chars(result.sources)
        return _category(
            "system",
            "System Quality",
            [
                _metric(
                    "latency_score",
                    "Latency Score",
                    "system",
                    _latency_score(result.latency_ms, good_ms=2_000, warn_ms=8_000),
                    f"{result.latency_ms} ms",
                    "Real query-flow latency for this benchmark case.",
                ),
                _metric(
                    "context_volume",
                    "Context Volume",
                    "system",
                    _volume_score(evidence_chars),
                    f"{evidence_chars} chars",
                    "Large evidence packets increase prompt cost and latency.",
                ),
            ],
        )


def _unique_sections(sources: list[SourceSnippet]) -> list[str]:
    seen: set[str] = set()
    sections: list[str] = []
    for source in sources:
        section = source.section_number
        if not section or section == "front_matter" or section in seen:
            continue
        seen.add(section)
        sections.append(section)
    return sections


def _content_tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", text.lower())
        if token not in STOP_WORDS
    ]


def _answer_overlap(expected: str, actual: str) -> float:
    expected_tokens = set(_content_tokens(expected))
    actual_tokens = set(_content_tokens(actual))
    if not expected_tokens:
        return 1.0
    return len(expected_tokens & actual_tokens) / len(expected_tokens)


def _category(key: str, label: str, metrics: list[EvaluationMetric]) -> EvaluationCategory:
    score = _average([metric.score for metric in metrics])
    return EvaluationCategory(
        key=key,
        label=label,
        score=round(score, 3),
        status=_status(score),
        metrics=metrics,
    )


def _metric(key: str, label: str, category: str, score: float, value: str, details: str) -> EvaluationMetric:
    bounded = max(0.0, min(score, 1.0))
    return EvaluationMetric(
        key=key,
        label=label,
        category=category,
        score=round(bounded, 3),
        value=value,
        status=_status(bounded),
        details=details,
    )


def _status(score: float) -> str:
    if score >= 0.8:
        return "good"
    if score >= 0.5:
        return "warn"
    return "bad"


def _percent(score: float) -> str:
    return f"{round(score * 100)}%"


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _category_scores(case_results: list[EvaluationCaseResult], key: str) -> list[float]:
    return [
        category.score
        for result in case_results
        for category in result.categories
        if category.key == key
    ]


def _metric_scores(case_results: list[EvaluationCaseResult], category_key: str, metric_key: str) -> list[float]:
    return [
        metric.score
        for result in case_results
        for category in result.categories
        if category.key == category_key
        for metric in category.metrics
        if metric.key == metric_key
    ]


def _p95(latencies: list[int]) -> int:
    if not latencies:
        return 0
    ordered = sorted(latencies)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def _source_count_score(source_count: int) -> float:
    if source_count == 0:
        return 0.0
    if 2 <= source_count <= 8:
        return 1.0
    if source_count == 1 or source_count <= 12:
        return 0.7
    return 0.4


def _latency_score(latency_ms: int, good_ms: int, warn_ms: int) -> float:
    if latency_ms <= good_ms:
        return 1.0
    if latency_ms <= warn_ms:
        return 0.7
    return 0.3


def _volume_score(evidence_chars: int) -> float:
    if evidence_chars == 0:
        return 0.0
    if evidence_chars <= 6_000:
        return 1.0
    if evidence_chars <= 12_000:
        return 0.7
    return 0.4


def _context_chars(sources: list[SourceSnippet]) -> int:
    return sum(len(source.text) for source in sources)

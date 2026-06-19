"""SQLite adapter for benchmark evaluation history."""

from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from pathlib import Path

from assessment_app.services.evaluation.internal.ports import EvaluationRunRepository
from assessment_app.services.evaluation.public.models import (
    BenchmarkCase,
    EvaluationCaseResult,
    EvaluationCategory,
    EvaluationMetric,
    EvaluationRunDetail,
    EvaluationRunSummary,
)
from assessment_app.services.query.public.models import SourceSnippet


class SqliteEvaluationRepository:
    """Persist evaluation runs and case results in SQLite."""

    def __init__(self, sqlite_path: Path) -> None:
        self._sqlite_path = sqlite_path
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def save_run(self, detail: EvaluationRunDetail) -> None:
        """Store a run summary and all per-case results atomically."""
        summary = detail.summary
        with self._connect() as conn:
            conn.execute("BEGIN")
            conn.execute(
                """
                INSERT INTO evaluation_runs (
                    run_id, created_at, top_k, case_count, overall_score,
                    retrieval_score, answer_score, system_score, pass_rate,
                    average_latency_ms, p95_latency_ms, total_latency_ms,
                    config_snapshot, categories_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.run_id,
                    summary.created_at,
                    summary.top_k,
                    summary.case_count,
                    summary.overall_score,
                    summary.retrieval_score,
                    summary.answer_score,
                    summary.system_score,
                    summary.pass_rate,
                    summary.average_latency_ms,
                    summary.p95_latency_ms,
                    summary.total_latency_ms,
                    summary.config_snapshot,
                    _dump_categories(detail.categories),
                ),
            )
            conn.executemany(
                """
                INSERT INTO evaluation_case_results (
                    run_id, position, case_id, query, expected_answer,
                    expected_section_numbers_json, answer_type, tags_json,
                    answer, answer_found, retrieved_section_numbers_json,
                    latency_ms, passed, categories_json, sources_json
                    , trace_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        summary.run_id,
                        position,
                        case_result.case.id,
                        case_result.case.query,
                        case_result.case.expected_answer,
                        json.dumps(case_result.expected_section_numbers),
                        case_result.case.answer_type,
                        json.dumps(case_result.case.tags),
                        case_result.answer,
                        int(case_result.answer_found),
                        json.dumps(case_result.retrieved_section_numbers),
                        case_result.latency_ms,
                        int(case_result.passed),
                        _dump_categories(case_result.categories),
                        json.dumps([asdict(source) for source in case_result.sources]),
                        json.dumps(asdict(case_result.trace)) if case_result.trace else None,
                    )
                    for position, case_result in enumerate(detail.cases)
                ],
            )
            conn.commit()

    def list_runs(self, limit: int) -> list[EvaluationRunSummary]:
        """Return run summaries, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM evaluation_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_summary_from_row(row) for row in rows]

    def get_run(self, run_id: str) -> EvaluationRunDetail | None:
        """Return one run detail or None."""
        with self._connect() as conn:
            run_row = conn.execute(
                "SELECT * FROM evaluation_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if run_row is None:
                return None

            case_rows = conn.execute(
                """
                SELECT *
                FROM evaluation_case_results
                WHERE run_id = ?
                ORDER BY position ASC
                """,
                (run_id,),
            ).fetchall()

        return EvaluationRunDetail(
            summary=_summary_from_row(run_row),
            categories=_categories_from_json(run_row["categories_json"]),
            cases=[_case_result_from_row(row) for row in case_rows],
        )

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    top_k INTEGER,
                    case_count INTEGER NOT NULL,
                    overall_score REAL NOT NULL,
                    retrieval_score REAL NOT NULL,
                    answer_score REAL NOT NULL,
                    system_score REAL NOT NULL,
                    pass_rate REAL NOT NULL,
                    average_latency_ms REAL NOT NULL,
                    p95_latency_ms INTEGER NOT NULL,
                    total_latency_ms INTEGER NOT NULL,
                    config_snapshot TEXT NOT NULL,
                    categories_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evaluation_case_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    case_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    expected_answer TEXT NOT NULL,
                    expected_section_numbers_json TEXT NOT NULL,
                    answer_type TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    answer_found INTEGER NOT NULL,
                    retrieved_section_numbers_json TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    passed INTEGER NOT NULL,
                    categories_json TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    trace_json TEXT,
                    FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id)
                );
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(evaluation_case_results)").fetchall()
            }
            if "trace_json" not in columns:
                conn.execute("ALTER TABLE evaluation_case_results ADD COLUMN trace_json TEXT")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn


def _summary_from_row(row: sqlite3.Row) -> EvaluationRunSummary:
    return EvaluationRunSummary(
        run_id=row["run_id"],
        created_at=row["created_at"],
        top_k=row["top_k"],
        case_count=row["case_count"],
        overall_score=row["overall_score"],
        retrieval_score=row["retrieval_score"],
        answer_score=row["answer_score"],
        system_score=row["system_score"],
        pass_rate=row["pass_rate"],
        average_latency_ms=row["average_latency_ms"],
        p95_latency_ms=row["p95_latency_ms"],
        total_latency_ms=row["total_latency_ms"],
        config_snapshot=row["config_snapshot"],
    )


def _case_result_from_row(row: sqlite3.Row) -> EvaluationCaseResult:
    expected_sections = json.loads(row["expected_section_numbers_json"])
    return EvaluationCaseResult(
        case=BenchmarkCase(
            id=row["case_id"],
            query=row["query"],
            expected_answer=row["expected_answer"],
            expected_section_numbers=expected_sections,
            answer_type=row["answer_type"],
            tags=json.loads(row["tags_json"]),
        ),
        answer=row["answer"],
        answer_found=bool(row["answer_found"]),
        expected_section_numbers=expected_sections,
        retrieved_section_numbers=json.loads(row["retrieved_section_numbers_json"]),
        latency_ms=row["latency_ms"],
        passed=bool(row["passed"]),
        categories=_categories_from_json(row["categories_json"]),
        sources=[SourceSnippet(**payload) for payload in json.loads(row["sources_json"])],
        trace=_trace_from_json(row["trace_json"]) if "trace_json" in row.keys() and row["trace_json"] else None,
    )


def _dump_categories(categories: list[EvaluationCategory]) -> str:
    return json.dumps([asdict(category) for category in categories])


def _categories_from_json(value: str) -> list[EvaluationCategory]:
    categories = json.loads(value)
    return [
        EvaluationCategory(
            key=category["key"],
            label=category["label"],
            score=category["score"],
            status=category["status"],
            metrics=[EvaluationMetric(**metric) for metric in category["metrics"]],
        )
        for category in categories
    ]


def _trace_from_json(value: str):
    from assessment_app.services.query.public.models import (
        QueryTrace,
        RetrievalStepTrace,
        TraceCandidate,
        VerificationResult,
    )

    payload = json.loads(value)
    return QueryTrace(
        original_query=payload["original_query"],
        retrieval_steps=[
            RetrievalStepTrace(
                query_id=step["query_id"],
                query=step["query"],
                expanded_query=step["expanded_query"],
                explicit_sections=step["explicit_sections"],
                validated_sections=step["validated_sections"],
                vector_candidates=[TraceCandidate(**item) for item in step["vector_candidates"]],
                lexical_candidates=[TraceCandidate(**item) for item in step["lexical_candidates"]],
                reranked_candidates=[TraceCandidate(**item) for item in step["reranked_candidates"]],
                verifier=VerificationResult(**step["verifier"]) if step.get("verifier") else None,
                expansion_actions=step.get("expansion_actions"),
            )
            for step in payload["retrieval_steps"]
        ],
        final_sources=[TraceCandidate(**item) for item in payload["final_sources"]],
    )


_: EvaluationRunRepository = SqliteEvaluationRepository.__new__(SqliteEvaluationRepository)  # type: ignore[assignment]

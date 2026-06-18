"""Integration tests for SqliteQueryLogger."""

from assessment_app.infra.sqlite.sqlite_query_logger import SqliteQueryLogger
from assessment_app.services.query.public.models import QueryLogEntry


def test_query_logger_analytics(tmp_path):
    logger = SqliteQueryLogger(tmp_path / "usage.db")
    logger.log_query(QueryLogEntry("known?", "yes", True, 100, "[]"))
    logger.log_query(QueryLogEntry("unknown?", "no", False, 300, "[]"))
    logger.log_query(QueryLogEntry("known?", "yes", True, 200, "[]"))

    assert logger.total_queries() == 3
    assert round(logger.answer_found_rate(), 2) == 0.67
    assert logger.average_latency_ms() == 200
    assert logger.frequent_questions(1)[0]["query"] == "known?"
    assert logger.no_answer_queries(1)[0]["query"] == "unknown?"

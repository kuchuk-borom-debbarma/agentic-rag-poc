"""Unit tests for DefaultAnalyticsService."""

from assessment_app.services.analytics.internal.service_impl import DefaultAnalyticsService
from tests.fakes.fake_analytics_reader import FakeAnalyticsReader


def test_analytics_service_returns_summary_from_reader():
    reader = FakeAnalyticsReader(
        total=5,
        found_rate=0.8,
        avg_latency=250.0,
        frequent=[{"query": "What?", "count": 3}],
        no_answer=[{"query": "Unknown?", "created_at": "2026-01-01"}],
    )

    service = DefaultAnalyticsService(analytics_reader=reader)
    summary = service.summary()

    assert summary.total_queries == 5
    assert summary.answer_found_rate == 0.8
    assert summary.average_latency_ms == 250.0
    assert summary.frequent_questions[0]["query"] == "What?"
    assert summary.no_answer_queries[0]["query"] == "Unknown?"

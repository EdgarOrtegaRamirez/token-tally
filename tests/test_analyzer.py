"""Tests for usage analyzer."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from token_tally.models import Provider, UsageEntry
from token_tally.storage import TokenStorage
from token_tally.analyzer import UsageAnalyzer


@pytest.fixture
def analyzer():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        store = TokenStorage(db_path)
        yield UsageAnalyzer(store)
    finally:
        store.close()
        os.unlink(db_path)


@pytest.fixture
def populated_storage():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        store = TokenStorage(db_path)
        now = datetime.now(timezone.utc)
        for day_offset in range(7):
            for model in ["gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet"]:
                for _ in range(2):
                    store.add_entry(UsageEntry(
                        model=model,
                        provider=Provider.OPENAI if "gpt" in model else Provider.ANTHROPIC,
                        input_tokens=500 + day_offset * 100,
                        output_tokens=200 + day_offset * 50,
                        duration_seconds=5.0 + day_offset,
                        project="test-project",
                        timestamp=now - timedelta(days=day_offset),
                    ))
        yield store
    finally:
        store.close()
        os.unlink(db_path)


class TestGetOverview:
    def test_overview_empty(self, analyzer):
        overview = analyzer.get_overview()
        assert overview["total_cost"] == 0.0
        assert overview["total_tokens"] == 0
        assert overview["total_requests"] == 0
        assert overview["projects"] == []
        assert overview["models"] == []

    def test_overview_with_data(self, populated_storage):
        analyzer = UsageAnalyzer(populated_storage)
        overview = analyzer.get_overview()
        assert overview["total_cost"] > 0
        assert overview["total_tokens"] > 0
        assert overview["total_requests"] > 0
        assert "test-project" in overview["projects"]


class TestCostBreakdown:
    def test_breakdown_empty(self, analyzer):
        assert analyzer.get_cost_breakdown() == []

    def test_breakdown_sorted(self, populated_storage):
        analyzer = UsageAnalyzer(populated_storage)
        breakdown = analyzer.get_cost_breakdown()
        assert len(breakdown) > 0
        for i in range(len(breakdown) - 1):
            assert breakdown[i]["cost"] >= breakdown[i + 1]["cost"]


class TestTrendAnalysis:
    def test_trend_insufficient_data(self, analyzer):
        assert isinstance(analyzer.get_trend_analysis(), list)

    def test_trend_with_data(self, populated_storage):
        analyzer = UsageAnalyzer(populated_storage)
        trend = analyzer.get_trend_analysis(days=30)
        assert isinstance(trend, dict)
        assert "trend_direction" in trend
        assert trend["trend_direction"] in ["increasing", "decreasing", "stable"]


class TestBudgetAlerts:
    def test_budget_alerts_have_expensive_models(self, analyzer):
        """Expensive model alerts are always included."""
        alerts = analyzer.get_budget_alerts(daily_budget=1000.0, monthly_budget=10000.0)
        assert len(alerts) >= 2  # gpt-4 and claude-3-opus expensive models

    def test_daily_budget_alert(self, analyzer):
        analyzer.storage.add_entry(UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=10_000_000, output_tokens=5_000_000,
        ))
        alerts = analyzer.get_budget_alerts(daily_budget=1.0, monthly_budget=100.0)
        assert len(alerts) > 0

    def test_alert_has_severity(self, analyzer):
        analyzer.storage.add_entry(UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=10_000_000, output_tokens=5_000_000,
        ))
        alerts = analyzer.get_budget_alerts(daily_budget=1.0, monthly_budget=100.0)
        for alert in alerts:
            assert "severity" in alert
            assert alert["severity"] in ["critical", "high", "medium", "low"]
            assert "message" in alert

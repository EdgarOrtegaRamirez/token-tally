"""Tests for token usage models."""

import pytest
from token_tally.models import (
    Provider, ModelInfo, UsageEntry, CostSummary, MODEL_CATALOG,
)


class TestProvider:
    def test_provider_values(self):
        values = [p.value for p in Provider]
        assert "openai" in values
        assert "anthropic" in values
        assert "google" in values
        assert "groq" in values
        assert "openrouter" in values
        assert "local" in values


class TestModelInfo:
    def test_create_model_info(self):
        model = ModelInfo(
            name="test-model", provider=Provider.OPENAI,
            input_price_per_million=5.00, output_price_per_million=15.00,
            max_context=8192,
        )
        assert model.name == "test-model"
        assert model.provider == Provider.OPENAI
        assert model.input_price_per_million == 5.00
        assert model.output_price_per_million == 15.00
        assert model.max_context == 8192
        assert model.supports_images is False
        assert model.supports_tools is False

    def test_model_info_validation(self):
        with pytest.raises(Exception):
            ModelInfo(
                name="bad-model", provider=Provider.OPENAI,
                input_price_per_million=-1, output_price_per_million=15.00,
                max_context=8192,
            )

    def test_model_catalog_has_entries(self):
        assert "gpt-4o" in MODEL_CATALOG
        assert "claude-3.5-sonnet" in MODEL_CATALOG
        assert "gemini-1.5-pro" in MODEL_CATALOG
        assert len(MODEL_CATALOG) > 5


class TestUsageEntry:
    def test_create_entry(self):
        entry = UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=50,
        )
        assert entry.total_tokens == 150
        assert entry.input_tokens == 100
        assert entry.output_tokens == 50
        assert entry.estimated_cost_usd > 0
        assert entry.task_type == "general"
        assert entry.metadata == {}

    def test_cost_calculation_gpt4o(self):
        entry = UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=10000, output_tokens=5000,
        )
        expected = (10000 * 2.50 / 1_000_000) + (5000 * 10.00 / 1_000_000)
        assert abs(entry.estimated_cost_usd - expected) < 0.0001

    def test_cost_calculation_claude(self):
        entry = UsageEntry(
            model="claude-3.5-sonnet", provider=Provider.ANTHROPIC,
            input_tokens=5000, output_tokens=3000,
        )
        expected = (5000 * 3.00 / 1_000_000) + (3000 * 15.00 / 1_000_000)
        assert abs(entry.estimated_cost_usd - expected) < 0.0001

    def test_cost_calculation_unknown_model(self):
        entry = UsageEntry(
            model="unknown-model-xyz", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=100,
        )
        assert entry.estimated_cost_usd > 0
        expected = (100 * 10.00 / 1_000_000) + (100 * 30.00 / 1_000_000)
        assert abs(entry.estimated_cost_usd - expected) < 0.0001

    def test_cost_per_thousand(self):
        entry = UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=1000, output_tokens=0,
        )
        assert entry.cost_per_thousand > 0

    def test_cost_per_thousand_zero_tokens(self):
        entry = UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=0, output_tokens=0,
        )
        assert entry.cost_per_thousand == 0.0

    def test_tokens_per_second(self):
        entry = UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=500, duration_seconds=10.0,
        )
        assert entry.tokens_per_second == 50.0

    def test_tokens_per_second_zero_duration(self):
        entry = UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=500, duration_seconds=0.0,
        )
        assert entry.tokens_per_second == 0.0

    def test_entry_with_metadata(self):
        entry = UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=50,
            metadata={"user_id": "user123", "api_endpoint": "/chat"},
        )
        assert entry.metadata["user_id"] == "user123"
        assert entry.metadata["api_endpoint"] == "/chat"

    def test_entry_with_task_type(self):
        entry = UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=50, task_type="code_generation",
        )
        assert entry.task_type == "code_generation"

    def test_entry_with_session(self):
        entry = UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=50,
            session="session-abc-123", project="my-project",
        )
        assert entry.session == "session-abc-123"
        assert entry.project == "my-project"

    def test_zero_output_tokens(self):
        entry = UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=0,
        )
        assert entry.total_tokens == 100
        assert entry.estimated_cost_usd > 0

    def test_timestamp_is_set(self):
        entry = UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=50,
        )
        assert entry.timestamp.tzinfo is not None or entry.timestamp.utcoffset() is not None


class TestCostSummary:
    def test_formatted_total_cost_dollars(self):
        summary = CostSummary(project="test", total_cost_usd=5.50)
        assert summary.formatted_total_cost == "$5.50"

    def test_formatted_total_cost_cents(self):
        summary = CostSummary(project="test", total_cost_usd=0.005)
        assert "¢" in summary.formatted_total_cost

    def test_formatted_average_cost(self):
        summary = CostSummary(project="test", total_cost_usd=10.0, entry_count=5, average_cost_per_request=2.00)
        assert summary.formatted_average_cost == "$2.00"

    def test_formatted_zero_average(self):
        summary = CostSummary(project="test", total_cost_usd=0.0, entry_count=0)
        assert summary.formatted_average_cost == "$0.00"

    def test_summary_with_breakdown(self):
        summary = CostSummary(
            project="test", total_cost_usd=10.0, entry_count=2,
            model_breakdown={"gpt-4o": {"tokens": 5000, "cost": 7.0}},
            provider_breakdown={"openai": {"tokens": 5000, "cost": 7.0}},
        )
        assert "gpt-4o" in summary.model_breakdown
        assert "openai" in summary.provider_breakdown

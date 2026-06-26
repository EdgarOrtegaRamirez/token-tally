"""Tests for token storage."""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from token_tally.models import Provider, UsageEntry
from token_tally.storage import DatabaseError, TokenStorage


@pytest.fixture
def storage():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        store = TokenStorage(db_path)
        yield store
    finally:
        store.close()
        os.unlink(db_path)


@pytest.fixture
def sample_entry():
    return UsageEntry(
        model="gpt-4o", provider=Provider.OPENAI,
        input_tokens=1000, output_tokens=500, duration_seconds=5.0,
        project="test-project", session="test-session", task_type="chat",
    )


class TestStorageInit:
    def test_create_storage(self, storage):
        assert storage.db_path is not None
        assert os.path.exists(storage.db_path)

    def test_tables_created(self, storage):
        conn = storage._get_conn()
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        assert "usage_entries" in tables
        assert "models" in tables

    def test_indexes_created(self, storage):
        conn = storage._get_conn()
        indexes = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()]
        assert "idx_usage_project" in indexes


class TestAddEntry:
    def test_add_entry(self, storage, sample_entry):
        entry_id = storage.add_entry(sample_entry)
        assert entry_id == sample_entry.id
        entries = storage.get_entries()
        assert len(entries) == 1

    def test_add_multiple_entries(self, storage):
        for i in range(5):
            entry = UsageEntry(
                model="gpt-4o", provider=Provider.OPENAI,
                input_tokens=100 + i * 10, output_tokens=50 + i * 5,
            )
            storage.add_entry(entry)
        assert len(storage.get_entries()) == 5

    def test_add_entry_custom_project(self, storage):
        entry = UsageEntry(
            model="claude-3.5-sonnet", provider=Provider.ANTHROPIC,
            input_tokens=200, output_tokens=100, project="my-project",
        )
        storage.add_entry(entry)
        assert len(storage.get_entries(project="my-project")) == 1

    def test_add_entry_metadata(self, storage):
        entry = UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=50,
            metadata={"user_id": "test123", "endpoint": "/v1/chat"},
        )
        storage.add_entry(entry)
        entries = storage.get_entries()
        assert entries[0].metadata["user_id"] == "test123"


class TestQueryEntries:
    def test_get_all_entries(self, storage):
        for _ in range(3):
            entry = UsageEntry(
                model="gpt-4o", provider=Provider.OPENAI,
                input_tokens=100, output_tokens=50,
            )
            storage.add_entry(entry)
        assert len(storage.get_entries()) == 3

    def test_filter_by_project(self, storage):
        for project in ["proj-a", "proj-b"]:
            entry = UsageEntry(
                model="gpt-4o", provider=Provider.OPENAI,
                input_tokens=100, output_tokens=50, project=project,
            )
            storage.add_entry(entry)
        assert len(storage.get_entries(project="proj-a")) == 1
        assert len(storage.get_entries(project="proj-b")) == 1

    def test_filter_by_provider(self, storage):
        storage.add_entry(UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=50,
        ))
        storage.add_entry(UsageEntry(
            model="claude-3.5-sonnet", provider=Provider.ANTHROPIC,
            input_tokens=100, output_tokens=50,
        ))
        assert len(storage.get_entries(provider=Provider.OPENAI)) == 1
        assert len(storage.get_entries(provider=Provider.ANTHROPIC)) == 1

    def test_filter_by_model(self, storage):
        for model in ["gpt-4o", "gpt-4-turbo", "claude-3.5-sonnet"]:
            storage.add_entry(UsageEntry(
                model=model, provider=Provider.OPENAI,
                input_tokens=100, output_tokens=50,
            ))
        assert len(storage.get_entries(model="gpt-4o")) == 1

    def test_limit(self, storage):
        for _ in range(10):
            storage.add_entry(UsageEntry(
                model="gpt-4o", provider=Provider.OPENAI,
                input_tokens=100, output_tokens=50,
            ))
        assert len(storage.get_entries(limit=5)) == 5

    def test_empty_result(self, storage):
        assert storage.get_entries(project="nonexistent") == []


class TestGetLists:
    def test_get_all_projects(self, storage):
        for project in ["proj-a", "proj-b", "proj-a"]:
            storage.add_entry(UsageEntry(
                model="gpt-4o", provider=Provider.OPENAI,
                input_tokens=100, output_tokens=50, project=project,
            ))
        projects = storage.get_all_projects()
        assert "proj-a" in projects
        assert "proj-b" in projects
        assert len(projects) == 2

    def test_get_all_models(self, storage):
        for model in ["gpt-4o", "claude-3.5-sonnet", "gpt-4o"]:
            storage.add_entry(UsageEntry(
                model=model, provider=Provider.OPENAI,
                input_tokens=100, output_tokens=50,
            ))
        models = storage.get_all_models()
        assert "gpt-4o" in models
        assert "claude-3.5-sonnet" in models
        assert len(models) == 2


class TestCostSummary:
    def test_basic_summary(self, storage):
        storage.add_entry(UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=1000, output_tokens=500,
        ))
        summary = storage.get_cost_summary()
        assert summary.total_input_tokens == 1000
        assert summary.total_output_tokens == 500
        assert summary.total_tokens == 1500
        assert summary.entry_count == 1
        assert summary.total_cost_usd > 0

    def test_summary_aggregation(self, storage):
        for _ in range(3):
            storage.add_entry(UsageEntry(
                model="gpt-4o", provider=Provider.OPENAI,
                input_tokens=100, output_tokens=50,
            ))
        summary = storage.get_cost_summary()
        assert summary.total_input_tokens == 300
        assert summary.total_output_tokens == 150
        assert summary.total_tokens == 450
        assert summary.entry_count == 3

    def test_summary_model_breakdown(self, storage):
        for model in ["gpt-4o", "claude-3.5-sonnet"]:
            for _ in range(2):
                storage.add_entry(UsageEntry(
                    model=model, provider=Provider.OPENAI,
                    input_tokens=100, output_tokens=50,
                ))
        summary = storage.get_cost_summary()
        assert "gpt-4o" in summary.model_breakdown
        assert "claude-3.5-sonnet" in summary.model_breakdown

    def test_summary_with_filters(self, storage):
        storage.add_entry(UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=50, project="proj-a",
        ))
        storage.add_entry(UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=50, project="proj-b",
        ))
        assert storage.get_cost_summary(project="proj-a").total_input_tokens == 100
        assert storage.get_cost_summary(project="proj-b").total_input_tokens == 100


class TestClearEntries:
    def test_clear_all(self, storage):
        for _ in range(5):
            storage.add_entry(UsageEntry(
                model="gpt-4o", provider=Provider.OPENAI,
                input_tokens=100, output_tokens=50,
            ))
        count = storage.clear_entries()
        assert count == 5
        assert len(storage.get_entries()) == 0

    def test_clear_project(self, storage):
        storage.add_entry(UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=50, project="proj-a",
        ))
        storage.add_entry(UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=50, project="proj-b",
        ))
        storage.add_entry(UsageEntry(
            model="gpt-4o", provider=Provider.OPENAI,
            input_tokens=100, output_tokens=50, project="proj-b",
        ))
        count = storage.clear_entries(project="proj-a")
        assert count == 1
        assert len(storage.get_entries()) == 2


class TestDailyStats:
    def test_daily_stats_empty(self, storage):
        assert storage.get_daily_stats(days=30) == []

    def test_daily_stats_with_data(self, storage):
        now = datetime.now(timezone.utc)
        for day_offset in range(5):
            ts = now - timedelta(days=day_offset)
            storage.add_entry(UsageEntry(
                model="gpt-4o", provider=Provider.OPENAI,
                input_tokens=100, output_tokens=50, timestamp=ts,
            ))
        stats = storage.get_daily_stats(days=30)
        assert len(stats) > 0


class TestContextManager:
    def test_context_manager(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            with TokenStorage(db_path) as storage:
                storage.add_entry(UsageEntry(
                    model="gpt-4o", provider=Provider.OPENAI,
                    input_tokens=100, output_tokens=50,
                ))
                assert len(storage.get_entries()) == 1
            assert storage._conn is None
        finally:
            os.unlink(db_path)

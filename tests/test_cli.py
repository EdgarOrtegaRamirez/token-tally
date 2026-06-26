"""Tests for CLI commands."""

import json
import os
import tempfile

import pytest
from click.testing import CliRunner

from token_tally.cli import main


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def runner_with_db(db_path):
    return CliRunner(), db_path


class TestCLIAdd:
    def test_add_entry(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, [
            "--db-path", db_path, "add",
            "--model", "gpt-4o", "--provider", "openai",
            "--input-tokens", "1000", "--output-tokens", "500",
            "--duration", "5.0", "--project", "test",
        ])
        assert result.exit_code == 0
        assert "Recorded" in result.output

    def test_add_invalid_provider(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, [
            "--db-path", db_path, "add",
            "--model", "gpt-4o", "--provider", "invalid",
            "--input-tokens", "100", "--output-tokens", "50",
        ])
        assert result.exit_code == 1
        assert "Invalid provider" in result.output

    def test_add_negative_input(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, [
            "--db-path", db_path, "add",
            "--model", "gpt-4o", "--provider", "openai",
            "--input-tokens", "-1", "--output-tokens", "50",
        ])
        assert result.exit_code == 1
        assert "cannot be negative" in result.output

    def test_add_negative_output(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, [
            "--db-path", db_path, "add",
            "--model", "gpt-4o", "--provider", "openai",
            "--input-tokens", "100", "--output-tokens", "-1",
        ])
        assert result.exit_code == 1
        assert "cannot be negative" in result.output

    def test_add_with_metadata(self, runner_with_db):
        runner, db_path = runner_with_db
        metadata = json.dumps({"user_id": "test123", "endpoint": "/chat"})
        result = runner.invoke(main, [
            "--db-path", db_path, "add",
            "--model", "gpt-4o", "--provider", "openai",
            "--input-tokens", "100", "--output-tokens", "50",
            "--metadata", metadata,
        ])
        assert result.exit_code == 0

    def test_add_invalid_metadata(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, [
            "--db-path", db_path, "add",
            "--model", "gpt-4o", "--provider", "openai",
            "--input-tokens", "100", "--output-tokens", "50",
            "--metadata", "not-valid-json",
        ])
        assert result.exit_code == 1
        assert "Invalid JSON" in result.output

    def test_add_claude(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, [
            "--db-path", db_path, "add",
            "--model", "claude-3.5-sonnet", "--provider", "anthropic",
            "--input-tokens", "2000", "--output-tokens", "1000",
        ])
        assert result.exit_code == 0


class TestCLIList:
    def test_list_empty(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, ["--db-path", db_path, "list"])
        assert result.exit_code == 0
        assert "No usage entries" in result.output

    def test_list_with_entries(self, runner_with_db):
        runner, db_path = runner_with_db
        runner.invoke(main, [
            "--db-path", db_path, "add",
            "--model", "gpt-4o", "--provider", "openai",
            "--input-tokens", "100", "--output-tokens", "50",
        ])
        result = runner.invoke(main, ["--db-path", db_path, "list"])
        assert result.exit_code == 0
        assert "gpt-4o" in result.output


class TestCLISummary:
    def test_summary_empty(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, ["--db-path", db_path, "summary"])
        assert result.exit_code == 0

    def test_summary_with_data(self, runner_with_db):
        runner, db_path = runner_with_db
        runner.invoke(main, [
            "--db-path", db_path, "add",
            "--model", "gpt-4o", "--provider", "openai",
            "--input-tokens", "1000", "--output-tokens", "500",
        ])
        result = runner.invoke(main, ["--db-path", db_path, "summary"])
        assert result.exit_code == 0
        assert "Token Usage Summary" in result.output


class TestCLIClear:
    def test_clear_all(self, runner_with_db):
        runner, db_path = runner_with_db
        runner.invoke(main, [
            "--db-path", db_path, "add",
            "--model", "gpt-4o", "--provider", "openai",
            "--input-tokens", "100", "--output-tokens", "50",
        ])
        result = runner.invoke(main, ["--db-path", db_path, "clear"])
        assert result.exit_code == 0
        assert "Cleared" in result.output

    def test_clear_project(self, runner_with_db):
        runner, db_path = runner_with_db
        runner.invoke(main, [
            "--db-path", db_path, "add",
            "--model", "gpt-4o", "--provider", "openai",
            "--input-tokens", "100", "--output-tokens", "50",
            "--project", "test-proj",
        ])
        result = runner.invoke(main, ["--db-path", db_path, "clear", "--project", "test-proj"])
        assert result.exit_code == 0
        assert "test-proj" in result.output


class TestCLIExport:
    def test_export_empty(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, ["--db-path", db_path, "export"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []

    def test_export_with_data(self, runner_with_db):
        runner, db_path = runner_with_db
        runner.invoke(main, [
            "--db-path", db_path, "add",
            "--model", "gpt-4o", "--provider", "openai",
            "--input-tokens", "100", "--output-tokens", "50",
        ])
        result = runner.invoke(main, ["--db-path", db_path, "export"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["model"] == "gpt-4o"


class TestCLIHelp:
    def test_help(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Token Tally" in result.output

    def test_add_help(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, ["--db-path", db_path, "add", "--help"])
        assert result.exit_code == 0
        assert "--model" in result.output

    def test_version(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, ["--db-path", db_path, "version"])
        assert result.exit_code == 0
        assert "Token Tally" in result.output
        assert "v" in result.output

    def test_sample_config(self, runner_with_db):
        runner, db_path = runner_with_db
        result = runner.invoke(main, ["--db-path", db_path, "sample-config"])
        assert result.exit_code == 0
        # The command prints a header panel + JSON; check for JSON keys in output
        assert "storage" in result.output
        assert "budget" in result.output

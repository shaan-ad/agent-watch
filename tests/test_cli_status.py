"""Tests for CLI status command."""

from __future__ import annotations

from click.testing import CliRunner

from agent_watch.cli.main import cli


def test_status_no_events(temp_storage):
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "No events found" in result.output


def test_status_with_events(sample_events, temp_storage):
    runner = CliRunner()
    result = runner.invoke(cli, ["status", "--days", "30"])
    assert result.exit_code == 0
    assert "Agent Runs" in result.output
    assert "Success Rate" in result.output

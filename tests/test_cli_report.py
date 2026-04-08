"""Tests for CLI report command."""

from __future__ import annotations

from click.testing import CliRunner

from agent_watch.cli.main import cli


def test_report_no_events(temp_storage):
    runner = CliRunner()
    result = runner.invoke(cli, ["report"])
    assert result.exit_code == 0
    assert "No events found" in result.output


def test_report_with_events(sample_events, temp_storage):
    runner = CliRunner()
    result = runner.invoke(cli, ["report", "--days", "30"])
    assert result.exit_code == 0
    assert "Agent Watch Report" in result.output
    assert "Overview" in result.output
    assert "Total Runs" in result.output

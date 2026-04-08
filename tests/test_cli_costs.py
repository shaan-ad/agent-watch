"""Tests for CLI costs command."""

from __future__ import annotations

from click.testing import CliRunner

from agent_watch.cli.main import cli


def test_costs_no_events(temp_storage):
    runner = CliRunner()
    result = runner.invoke(cli, ["costs"])
    assert result.exit_code == 0
    assert "No events found" in result.output


def test_costs_with_events(sample_events, temp_storage):
    runner = CliRunner()
    result = runner.invoke(cli, ["costs", "--days", "30"])
    assert result.exit_code == 0
    assert "Cost Report" in result.output
    assert "Total Cost" in result.output

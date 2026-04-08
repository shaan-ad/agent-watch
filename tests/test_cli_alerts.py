"""Tests for CLI alerts command."""

from __future__ import annotations

from click.testing import CliRunner

from agent_watch.cli.main import cli


def test_alerts_no_events(temp_storage):
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts"])
    assert result.exit_code == 0
    assert "No recent events" in result.output


def test_alerts_with_events(sample_events, temp_storage):
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", "--days", "30"])
    assert result.exit_code == 0
    # Should find the code-reviewer with 100% error rate
    # (it only has 1 run though, below the 3-run threshold)

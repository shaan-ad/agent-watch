"""agent-watch alerts: check for anomalies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import click

from agent_watch import otel
from agent_watch.cli.formatting import format_cost, format_percentage
from agent_watch.storage import aggregate_by_agent, load_spans


@click.command()
@click.option("--days", "-d", default=1, help="Check window in days (default: 1)")
@click.option("--compare", "-c", default=7, help="Compare against this many days (default: 7)")
def alerts_cmd(days: int, compare: int):
    """Check for cost spikes, error rate increases, and latency issues."""
    current = load_spans(days=days)
    baseline = load_spans(days=compare)

    if not current:
        click.echo("No recent events to analyze.")
        return

    # Filter baseline to exclude current period
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    baseline_only = [e for e in baseline if e.start_time < cutoff.timestamp()]

    alerts = []

    # Cost spike detection
    current_cost = sum(e.attributes.get(otel.AGENT_WATCH_COST_USD, 0.0) for e in current)
    if baseline_only:
        baseline_cost = sum(e.attributes.get(otel.AGENT_WATCH_COST_USD, 0.0) for e in baseline_only)
        baseline_days = compare - days
        if baseline_days > 0 and baseline_cost > 0:
            daily_baseline = baseline_cost / baseline_days
            daily_current = current_cost / days
            if daily_current > daily_baseline * 1.5:
                alerts.append(
                    f"COST SPIKE: Daily cost ({format_cost(daily_current)}/day) is "
                    f"{daily_current / daily_baseline:.1f}x the baseline "
                    f"({format_cost(daily_baseline)}/day)"
                )

    # Error rate detection
    current_agents = aggregate_by_agent(current)
    baseline_agents = aggregate_by_agent(baseline_only)

    for name, stats in current_agents.items():
        if stats.total_runs < 3:
            continue

        baseline_stats = baseline_agents.get(name)
        if baseline_stats and baseline_stats.total_runs >= 3:
            if stats.success_rate < baseline_stats.success_rate - 0.1:
                alerts.append(
                    f"ERROR SPIKE: {name} success rate dropped from "
                    f"{format_percentage(baseline_stats.success_rate)} to "
                    f"{format_percentage(stats.success_rate)}"
                )

        if stats.success_rate < 0.8:
            alerts.append(
                f"HIGH ERROR RATE: {name} has {format_percentage(1 - stats.success_rate)} "
                f"error rate ({stats.failures}/{stats.total_runs} failed)"
            )

    # Latency detection
    for name, stats in current_agents.items():
        if stats.total_runs < 3:
            continue
        baseline_stats = baseline_agents.get(name)
        if baseline_stats and baseline_stats.total_runs >= 3:
            if stats.avg_duration_ms > baseline_stats.avg_duration_ms * 1.5:
                alerts.append(
                    f"LATENCY INCREASE: {name} avg duration increased from "
                    f"{baseline_stats.avg_duration_ms:.0f}ms to "
                    f"{stats.avg_duration_ms:.0f}ms"
                )

    if alerts:
        click.echo(f"\n{len(alerts)} alert(s) found:")
        click.echo()
        for alert in alerts:
            click.echo(f"  ! {alert}")
    else:
        click.echo("\nNo alerts. Everything looks normal.")

    click.echo()

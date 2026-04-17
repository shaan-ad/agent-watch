"""agent-watch report: full markdown report with trends and recommendations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import click

from agent_watch import otel
from agent_watch.cli.formatting import bar_chart, format_cost, format_percentage, format_tokens
from agent_watch.storage import aggregate_by_agent, aggregate_by_model, load_events


@click.command()
@click.option("--days", "-d", default=7, help="Number of days to report on (default: 7)")
def report_cmd(days: int):
    """Generate a full analytics report."""
    previous_events = load_events(days=days * 2)

    # Split previous into "this period" and "last period"
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    current_events = [e for e in previous_events if e.start_time >= cutoff.timestamp()]
    prev_events = [e for e in previous_events if e.start_time < cutoff.timestamp()]

    if not current_events:
        click.echo("No events found for the reporting period.")
        return

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    start_str = start.strftime("%b %d")
    end_str = now.strftime("%b %d, %Y")

    click.echo(f"\nAgent Watch Report ({start_str} - {end_str})")
    click.echo("=" * 50)

    # Overview
    agent_runs = [e for e in current_events if e.kind == otel.KIND_AGENT]
    llm_calls = [e for e in current_events if e.kind == otel.KIND_LLM]
    total_runs = len(agent_runs)
    successes = sum(1 for e in agent_runs if e.status == otel.STATUS_OK)
    success_rate = successes / total_runs if total_runs > 0 else 0
    total_cost = sum(e.attributes.get(otel.AGENT_WATCH_COST_USD, 0.0) for e in current_events)
    total_input = sum(e.attributes.get(otel.GEN_AI_USAGE_INPUT_TOKENS, 0) for e in current_events)
    total_output = sum(e.attributes.get(otel.GEN_AI_USAGE_OUTPUT_TOKENS, 0) for e in current_events)

    click.echo("\nOverview:")
    click.echo(f"  Total Runs:     {total_runs}")
    click.echo(f"  LLM Calls:      {len(llm_calls)}")
    click.echo(f"  Success Rate:   {format_percentage(success_rate)}")
    click.echo(f"  Total Cost:     {format_cost(total_cost)}")
    click.echo(
        f"  Total Tokens:   {format_tokens(total_input + total_output)} "
        f"({format_tokens(total_input)} input, {format_tokens(total_output)} output)"
    )

    # Cost by agent
    agent_stats = aggregate_by_agent(current_events)
    if agent_stats:
        click.echo("\nCost by Agent:")
        sorted_agents = sorted(
            agent_stats.values(), key=lambda a: a.total_cost, reverse=True
        )
        max_cost = sorted_agents[0].total_cost if sorted_agents else 1
        for agent in sorted_agents:
            pct = agent.total_cost / total_cost if total_cost > 0 else 0
            bar = bar_chart(agent.total_cost, max_cost)
            click.echo(
                f"  {agent.name:<20} {format_cost(agent.total_cost):>8}  "
                f"({format_percentage(pct):>5})  {bar}"
            )

    # Cost by model
    model_stats = aggregate_by_model(current_events)
    if model_stats:
        click.echo("\nCost by Model:")
        sorted_models = sorted(
            model_stats.values(), key=lambda m: m.total_cost, reverse=True
        )
        for model in sorted_models:
            pct = model.total_cost / total_cost if total_cost > 0 else 0
            click.echo(
                f"  {model.model:<25} {format_cost(model.total_cost):>8}  "
                f"({format_percentage(pct):>5})"
            )

    # Trends
    if prev_events:
        prev_cost = sum(e.attributes.get(otel.AGENT_WATCH_COST_USD, 0.0) for e in prev_events)
        prev_runs = len([e for e in prev_events if e.kind == otel.KIND_AGENT])
        prev_errors = sum(
            1 for e in prev_events if e.kind == otel.KIND_AGENT and e.status == otel.STATUS_ERROR
        )
        current_errors = sum(1 for e in agent_runs if e.status == otel.STATUS_ERROR)
        prev_error_rate = prev_errors / prev_runs if prev_runs > 0 else 0
        current_error_rate = current_errors / total_runs if total_runs > 0 else 0

        click.echo(f"\nTrends (vs previous {days} days):")
        if prev_cost > 0:
            cost_change = ((total_cost - prev_cost) / prev_cost) * 100
            sign = "+" if cost_change >= 0 else ""
            click.echo(
                f"  Cost:         {sign}{cost_change:.1f}% "
                f"({format_cost(prev_cost)} -> {format_cost(total_cost)})"
            )
        if prev_runs > 0:
            run_change = ((total_runs - prev_runs) / prev_runs) * 100
            sign = "+" if run_change >= 0 else ""
            click.echo(f"  Runs:         {sign}{run_change:.1f}% ({prev_runs} -> {total_runs})")
        error_delta = current_error_rate - prev_error_rate
        sign = "+" if error_delta >= 0 else ""
        click.echo(
            f"  Error Rate:   {sign}{error_delta * 100:.1f}% "
            f"({format_percentage(prev_error_rate)} -> {format_percentage(current_error_rate)})"
        )

    # Anomalies
    anomalies = _detect_anomalies(current_events, agent_stats)
    if anomalies:
        click.echo("\nAnomalies:")
        for anomaly in anomalies:
            click.echo(f"  ! {anomaly}")

    # Recommendations
    recommendations = _generate_recommendations(agent_stats, model_stats, total_cost)
    if recommendations:
        click.echo("\nRecommendations:")
        for rec in recommendations:
            click.echo(f"  - {rec}")

    click.echo()


def _detect_anomalies(events, agent_stats):
    """Detect anomalies including per-day error rate spikes."""
    anomalies = []

    # Group agent_run events by agent name and day
    from collections import defaultdict

    daily_stats = defaultdict(lambda: defaultdict(lambda: {otel.STATUS_OK: 0, otel.STATUS_ERROR: 0}))
    for event in events:
        if event.kind != otel.KIND_AGENT:
            continue
        day = datetime.fromtimestamp(event.start_time, tz=timezone.utc).strftime("%b %-d")
        daily_stats[event.name][day][event.status] += 1

    # Detect per-day spikes vs overall rate
    for name, stats in agent_stats.items():
        if stats.total_runs < 3:
            continue

        overall_error_rate = 1 - stats.success_rate

        for day, counts in daily_stats.get(name, {}).items():
            day_total = counts[otel.STATUS_OK] + counts[otel.STATUS_ERROR]
            if day_total < 2:
                continue
            day_error_rate = counts[otel.STATUS_ERROR] / day_total

            # Spike: day error rate is significantly higher than overall
            if day_error_rate > overall_error_rate + 0.05 and day_error_rate >= 0.1:
                anomalies.append(
                    f"{name} error rate spiked from "
                    f"{format_percentage(overall_error_rate)} to "
                    f"{format_percentage(day_error_rate)} on {day}"
                )
            elif stats.success_rate < 0.85:
                # Fallback: flag agents with high overall error rate
                anomalies.append(
                    f"{name} has a {format_percentage(1 - stats.success_rate)} error rate "
                    f"({stats.failures} failures in {stats.total_runs} runs)"
                )

    return anomalies


def _generate_recommendations(agent_stats, model_stats, total_cost):
    """Generate actionable recommendations with error pattern detection."""
    recs = []

    if agent_stats:
        sorted_agents = sorted(
            agent_stats.values(), key=lambda a: a.total_cost, reverse=True
        )
        top = sorted_agents[0]
        if total_cost > 0 and top.total_cost / total_cost > 0.4:
            recs.append(
                f"{top.name} uses {format_percentage(top.total_cost / total_cost)} "
                f"of budget; consider cheaper model for initial pass"
            )

    for name, stats in (agent_stats or {}).items():
        if stats.failures > 0 and stats.success_rate < 0.9:
            pattern = _detect_error_pattern(stats)
            if pattern:
                recs.append(
                    f"Investigate {name} failures "
                    f"({stats.failures} errors, pattern: \"{pattern}\")"
                )
            else:
                recs.append(f"Investigate {name} failures ({stats.failures} errors)")

    return recs


def _detect_error_pattern(stats):
    """Find the most common error message pattern for an agent."""
    if not hasattr(stats, "error_messages") or not stats.error_messages:
        return None

    from collections import Counter
    counts = Counter(stats.error_messages)
    most_common, count = counts.most_common(1)[0]
    if count >= 2 or len(stats.error_messages) == 1:
        # Truncate long messages
        if len(most_common) > 50:
            return most_common[:50] + "..."
        return most_common
    return None

"""agent-watch traces: browse execution traces."""

from __future__ import annotations

import click

from agent_watch import otel
from agent_watch.cli.formatting import format_cost, format_duration
from agent_watch.storage import load_events


@click.command()
@click.option("--days", "-d", default=1, help="Number of days to look back (default: 1)")
@click.option("--agent", "-a", default=None, help="Filter by agent name")
@click.option("--status", "-s", type=click.Choice(["success", "error"]), default=None)
@click.option("--type", "-t", "event_type", type=click.Choice(["agent_run", "llm_call", "span"]), default=None)
@click.option("--limit", "-n", default=20, help="Max events to show (default: 20)")
def traces_cmd(days: int, agent: str, status: str, event_type: str, limit: int):
    """Browse execution traces."""
    spans = load_events(
        days=days,
        agent_name=agent,
        status=status,
        event_type=event_type,
    )

    if not spans:
        click.echo("No traces found matching your filters.")
        return

    # Sort by start time, most recent first
    spans.sort(key=lambda s: s.start_time, reverse=True)
    spans = spans[:limit]

    click.echo(f"\nTraces ({len(spans)} events)")
    click.echo("=" * 70)

    for span in spans:
        status_icon = "\u2713" if span.status == otel.STATUS_OK else "\u2717"
        cost = span.attributes.get(otel.AGENT_WATCH_COST_USD, 0.0)
        cost_str = format_cost(cost) if cost > 0 else ""
        duration_str = format_duration(span.duration_ms) if span.duration_ms > 0 else ""
        model = span.attributes.get(otel.GEN_AI_REQUEST_MODEL, "")

        parts = [
            f"  {status_icon} [{span.kind}]",
            span.name,
        ]
        if model:
            parts.append(f"({model})")
        if duration_str:
            parts.append(duration_str)
        if cost_str:
            parts.append(cost_str)

        click.echo(" ".join(parts))

        if span.error:
            click.echo(f"    Error: {span.error[:100]}")
        if span.input_preview:
            click.echo(f"    In:  {span.input_preview[:80]}")
        if span.output_preview:
            click.echo(f"    Out: {span.output_preview[:80]}")

    click.echo()

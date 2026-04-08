"""agent-watch traces: browse execution traces."""

from __future__ import annotations

import click

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
    events = load_events(
        days=days,
        agent_name=agent,
        status=status,
        event_type=event_type,
    )

    if not events:
        click.echo("No traces found matching your filters.")
        return

    # Sort by start time, most recent first
    events.sort(key=lambda e: e.start_time, reverse=True)
    events = events[:limit]

    click.echo(f"\nTraces ({len(events)} events)")
    click.echo("=" * 70)

    for event in events:
        status_icon = "\u2713" if event.status == "success" else "\u2717"
        cost = event.metadata.get("cost_usd", 0)
        cost_str = format_cost(cost) if cost > 0 else ""
        duration_str = format_duration(event.duration_ms) if event.duration_ms > 0 else ""
        model = event.metadata.get("model", "")

        parts = [
            f"  {status_icon} [{event.type}]",
            event.name,
        ]
        if model:
            parts.append(f"({model})")
        if duration_str:
            parts.append(duration_str)
        if cost_str:
            parts.append(cost_str)

        click.echo(" ".join(parts))

        if event.error:
            click.echo(f"    Error: {event.error[:100]}")
        if event.input_preview:
            click.echo(f"    In:  {event.input_preview[:80]}")
        if event.output_preview:
            click.echo(f"    Out: {event.output_preview[:80]}")

    click.echo()

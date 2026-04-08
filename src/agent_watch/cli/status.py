"""agent-watch status: summary of recent runs."""

from __future__ import annotations

import click

from agent_watch.cli.formatting import format_cost, format_percentage, format_tokens
from agent_watch.storage import aggregate_by_agent, load_events


@click.command()
@click.option("--days", "-d", default=1, help="Number of days to look back (default: 1)")
def status_cmd(days: int):
    """Show a summary of recent agent runs."""
    events = load_events(days=days)

    if not events:
        click.echo("No events found. Instrument your agents with @trace_agent to get started.")
        return

    agent_runs = [e for e in events if e.type == "agent_run"]
    llm_calls = [e for e in events if e.type == "llm_call"]

    total_runs = len(agent_runs)
    successes = sum(1 for e in agent_runs if e.status == "success")
    success_rate = successes / total_runs if total_runs > 0 else 0

    total_cost = sum(e.metadata.get("cost_usd", 0) for e in events)
    total_tokens = sum(
        e.metadata.get("input_tokens", 0) + e.metadata.get("output_tokens", 0)
        for e in events
    )

    click.echo(f"\nAgent Watch Status (last {days} day{'s' if days > 1 else ''})")
    click.echo("=" * 40)
    click.echo(f"  Agent Runs:    {total_runs}")
    click.echo(f"  LLM Calls:     {len(llm_calls)}")
    click.echo(f"  Success Rate:  {format_percentage(success_rate)}")
    click.echo(f"  Total Cost:    {format_cost(total_cost)}")
    click.echo(f"  Total Tokens:  {format_tokens(total_tokens)}")

    # Top agents
    agent_stats = aggregate_by_agent(events)
    if agent_stats:
        click.echo("\nTop Agents:")
        sorted_agents = sorted(
            agent_stats.values(), key=lambda a: a.total_runs, reverse=True
        )
        for agent in sorted_agents[:5]:
            click.echo(
                f"  {agent.name:<25} {agent.total_runs} runs  "
                f"{format_percentage(agent.success_rate)} success"
            )

    click.echo()

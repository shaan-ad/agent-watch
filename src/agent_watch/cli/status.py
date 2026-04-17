"""agent-watch status: summary of recent runs."""

from __future__ import annotations

import click

from agent_watch import otel
from agent_watch.cli.formatting import format_cost, format_percentage, format_tokens
from agent_watch.storage import aggregate_by_agent, load_spans


@click.command()
@click.option("--days", "-d", default=1, help="Number of days to look back (default: 1)")
def status_cmd(days: int):
    """Show a summary of recent agent runs."""
    spans = load_spans(days=days)

    if not spans:
        click.echo("No events found. Instrument your agents with @trace_agent to get started.")
        return

    agent_runs = [s for s in spans if s.kind == otel.KIND_AGENT]
    llm_calls = [s for s in spans if s.kind == otel.KIND_LLM]

    total_runs = len(agent_runs)
    successes = sum(1 for s in agent_runs if s.status == otel.STATUS_OK)
    success_rate = successes / total_runs if total_runs > 0 else 0

    total_cost = sum(s.attributes.get(otel.AGENT_WATCH_COST_USD, 0.0) for s in spans)
    total_tokens = sum(
        s.attributes.get(otel.GEN_AI_USAGE_INPUT_TOKENS, 0)
        + s.attributes.get(otel.GEN_AI_USAGE_OUTPUT_TOKENS, 0)
        for s in spans
    )

    click.echo(f"\nAgent Watch Status (last {days} day{'s' if days > 1 else ''})")
    click.echo("=" * 40)
    click.echo(f"  Agent Runs:    {total_runs}")
    click.echo(f"  LLM Calls:     {len(llm_calls)}")
    click.echo(f"  Success Rate:  {format_percentage(success_rate)}")
    click.echo(f"  Total Cost:    {format_cost(total_cost)}")
    click.echo(f"  Total Tokens:  {format_tokens(total_tokens)}")

    # Top agents
    agent_stats = aggregate_by_agent(spans)
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

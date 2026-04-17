"""agent-watch costs: token usage and cost breakdown."""

from __future__ import annotations

import click

from agent_watch import otel
from agent_watch.cli.formatting import bar_chart, format_cost, format_percentage, format_tokens
from agent_watch.storage import aggregate_by_agent, aggregate_by_model, load_spans


@click.command()
@click.option("--days", "-d", default=7, help="Number of days to look back (default: 7)")
@click.option("--by", type=click.Choice(["agent", "model", "both"]), default="both")
def costs_cmd(days: int, by: str):
    """Show cost breakdown by agent and/or model."""
    spans = load_spans(days=days)

    if not spans:
        click.echo("No events found.")
        return

    total_cost = sum(s.attributes.get(otel.AGENT_WATCH_COST_USD, 0.0) for s in spans)
    total_tokens = sum(
        s.attributes.get(otel.GEN_AI_USAGE_INPUT_TOKENS, 0)
        + s.attributes.get(otel.GEN_AI_USAGE_OUTPUT_TOKENS, 0)
        for s in spans
    )

    click.echo(f"\nCost Report (last {days} days)")
    click.echo("=" * 50)
    click.echo(f"  Total Cost:    {format_cost(total_cost)}")
    click.echo(f"  Total Tokens:  {format_tokens(total_tokens)}")
    click.echo()

    if by in ("agent", "both"):
        agent_stats = aggregate_by_agent(spans)
        if agent_stats:
            click.echo("Cost by Agent:")
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
            click.echo()

    if by in ("model", "both"):
        model_stats = aggregate_by_model(spans)
        if model_stats:
            click.echo("Cost by Model:")
            sorted_models = sorted(
                model_stats.values(), key=lambda m: m.total_cost, reverse=True
            )
            for model in sorted_models:
                pct = model.total_cost / total_cost if total_cost > 0 else 0
                click.echo(
                    f"  {model.model:<25} {format_cost(model.total_cost):>8}  "
                    f"({format_percentage(pct):>5})  "
                    f"{format_tokens(model.total_tokens)} tokens"
                )
            click.echo()

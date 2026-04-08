"""CLI entrypoint for Agent Watch."""

from __future__ import annotations

import click

from agent_watch.cli.status import status_cmd
from agent_watch.cli.costs import costs_cmd
from agent_watch.cli.traces import traces_cmd
from agent_watch.cli.report import report_cmd
from agent_watch.cli.alerts import alerts_cmd


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Agent Watch: observability for AI agents."""
    pass


cli.add_command(status_cmd, "status")
cli.add_command(costs_cmd, "costs")
cli.add_command(traces_cmd, "traces")
cli.add_command(report_cmd, "report")
cli.add_command(alerts_cmd, "alerts")


if __name__ == "__main__":
    cli()

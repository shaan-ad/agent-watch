# Agent Watch

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/shaan-ad/agent-watch/actions/workflows/ci.yml/badge.svg)](https://github.com/shaan-ad/agent-watch/actions)

**Observability for AI agents. Track cost, latency, and success rates with zero framework lock-in.**

Drop two decorators into your agent code. Get cost breakdowns, failure analysis, and trend reports from the CLI. No config, no external services, no vendor lock-in.

## Why This Exists

Every team deploying AI agents has the same blind spots: how much are we spending, which agents are failing, and is performance getting worse? Existing tools either require a specific framework, need a hosted backend, or cost money before you know if you need them.

Agent Watch is the missing `top` command for AI agents: local, fast, and framework-agnostic.

## Quick Start

```bash
pip install agent-watch
```

```python
from agent_watch import trace_agent, trace_llm_call

@trace_agent(name="research-agent")
async def research(topic: str) -> str:
    result = await call_llm(topic)
    return result

@trace_llm_call(model="claude-sonnet-4-20250514")
async def call_llm(prompt: str) -> dict:
    # Your LLM call here
    return {"content": "...", "input_tokens": 500, "output_tokens": 200}
```

```bash
agent-watch status    # What happened today?
agent-watch costs     # Where's the money going?
agent-watch report    # Full analytics report
```

## SDK

Three primitives that work with any code:

### `@trace_agent` - Trace agent functions

```python
from agent_watch import trace_agent

@trace_agent(name="code-reviewer", tags=["production"])
def review_code(files: list[str]) -> str:
    # Your agent logic
    return "Review complete"

# Works with async too
@trace_agent(name="data-analyst")
async def analyze(query: str) -> dict:
    ...
```

Captures: name, inputs, outputs, duration, success/failure, nested child spans.

### `@trace_llm_call` - Trace LLM calls

```python
from agent_watch import trace_llm_call

@trace_llm_call(model="claude-sonnet-4-20250514")
async def call_claude(prompt: str) -> dict:
    response = await client.messages.create(model="claude-sonnet-4-20250514", ...)
    return {
        "content": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
```

Captures: model, tokens, estimated cost (auto-calculated), latency.

### `Span` - Instrument any block of code

```python
from agent_watch import Span

with Span("data-preprocessing") as span:
    data = load_data()
    span.set_metadata("rows", len(data))
    cleaned = clean_data(data)
    span.set_output(f"Processed {len(cleaned)} rows")

# Async too
async with Span("api-call") as span:
    result = await fetch_external_api()
```

### Nesting

Traces nest automatically. An `@trace_agent` containing `@trace_llm_call` calls produces a parent-child trace tree:

```python
@trace_agent(name="research-agent")
async def research(topic):
    summary = await search_web(topic)      # traced as child
    analysis = await analyze(summary)       # traced as child
    return analysis
```

## CLI

### `agent-watch status`

Quick summary of recent activity:

```
$ agent-watch status

Agent Watch Status (last 1 day)
========================================
  Agent Runs:    47
  LLM Calls:     123
  Success Rate:  95.7%
  Total Cost:    $1.84
  Total Tokens:  312.5K
```

### `agent-watch costs`

Cost breakdown by agent and model:

```
$ agent-watch costs --days 7

Cost by Agent:
  research-agent      $5.21  (42.2%)  ████████████░░░░░░░░
  code-reviewer       $3.89  (31.5%)  █████████░░░░░░░░░░░

Cost by Model:
  claude-sonnet-4     $7.82  (63.4%)  312.5K tokens
  gpt-4o              $3.41  (27.6%)  98.2K tokens
```

### `agent-watch report`

Full analytics report with trends, anomalies, and recommendations:

```
$ agent-watch report --days 7

Trends (vs previous 7 days):
  Cost:         +8.2% ($11.40 -> $12.34)
  Runs:         +12.1% (755 -> 847)
  Error Rate:   +2.1% (3.1% -> 5.2%)

Anomalies:
  ! code-reviewer error rate spiked from 3% to 11% on Apr 7

Recommendations:
  - Investigate code-reviewer failures (12 errors, pattern: "context length exceeded")
  - research-agent uses 42% of budget; consider cheaper model for initial pass
```

### `agent-watch traces`

Browse individual execution traces:

```
$ agent-watch traces --agent research-agent --status error
```

### `agent-watch alerts`

Check for anomalies against baseline:

```
$ agent-watch alerts

  ! COST SPIKE: Daily cost ($4.21/day) is 2.3x the baseline ($1.83/day)
  ! ERROR SPIKE: code-reviewer success rate dropped from 97.0% to 89.0%
```

## How It Works

All telemetry writes to `.agent-watch/` as append-only JSONL files (one per day). The CLI reads these files to produce reports. No external services, no network calls.

```
.agent-watch/
  2026-04-07.jsonl
  2026-04-08.jsonl
```

### Cost Estimation

Built-in pricing for Claude, GPT-4, Gemini, and Llama models. Auto-calculates cost from token counts. Override with your own pricing via `AGENT_WATCH_PRICING` env var pointing to a YAML file.

## Architecture

```
src/agent_watch/
  decorators.py     # @trace_agent, @trace_llm_call
  span.py           # Span context manager
  collector.py      # Event capture and JSONL writing
  storage.py        # JSONL reading and querying
  cost.py           # Cost estimation from token counts
  types.py          # Event dataclasses
  cli/              # CLI commands (status, costs, traces, report, alerts)
```

## Coming Soon

Agent Watch is the open-source foundation. A hosted dashboard with real-time streaming, team features, and Slack/email alerting is in development.

## Contributing

```bash
git clone https://github.com/shaan-ad/agent-watch.git
cd agent-watch
pip install -e ".[dev]"
pytest -v
```

## License

MIT

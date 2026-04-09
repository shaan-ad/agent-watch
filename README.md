# Agent Watch

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/shaan-ad/agent-watch/actions/workflows/ci.yml/badge.svg)](https://github.com/shaan-ad/agent-watch/actions)

**Know what your agents cost before you get the bill.**

Two decorators. One CLI. Zero config. Agent Watch gives you cost, latency, and reliability data from the first time you run your agent. No accounts, no dashboards, no infrastructure. Just `pip install` and go.

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
    response = await client.messages.create(model="claude-sonnet-4-20250514", ...)
    return {
        "content": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
```

```bash
$ agent-watch status

  Agent Runs:    47
  LLM Calls:    123
  Success Rate:  95.7%
  Total Cost:    $1.84
  Total Tokens:  312.5K
```

That's it. You're tracking cost, latency, and success rates. No signup. No API key. No YAML config. The data stays on your machine as plain JSONL files you can grep, pipe, and script against.

## Why Agent Watch

You're building an agent. You run it a few times, eyeball the output, and ship it. Three weeks later, you get an LLM invoice and realize it's been burning $400/day. You've been flying blind since day one.

Every observability tool out there (Langfuse, LangSmith, Datadog, Arize) requires you to make a conscious decision to "adopt observability." Create an account, install an SDK, configure a dashboard, route your data to a cloud service. That decision happens *after* the pain, not before it.

Agent Watch is the tool you use *before* you need an observability tool. Add two decorators when you write the code, and cost/latency/reliability data is always there in your terminal. When you outgrow local analytics, export to whatever platform you choose.

**Agent Watch is to Datadog what `sqlite` is to PostgreSQL.** Start here. Graduate when you're ready.

## Quick Start

### 1. Install

```bash
pip install agent-watch
```

### 2. Add decorators

```python
from agent_watch import trace_agent, trace_llm_call

@trace_agent(name="code-reviewer", tags=["production"])
def review_code(files: list[str]) -> str:
    analysis = call_llm(files)
    return analysis

@trace_llm_call(model="gpt-4o")
def call_llm(prompt: str) -> dict:
    # Your LLM call (any provider, any framework)
    return {"content": "...", "input_tokens": 500, "output_tokens": 200}
```

### 3. Run your agent, then check the terminal

```bash
agent-watch status     # What happened today?
agent-watch costs      # Where's the money going?
agent-watch report     # Full analytics with trends
agent-watch alerts     # Anything look wrong?
```

No step 4. You're done.

## SDK

Three primitives. They work with any framework (LangChain, CrewAI, AutoGen, LangGraph) or no framework at all.

### `@trace_agent` -- Trace agent functions

```python
from agent_watch import trace_agent

@trace_agent(name="code-reviewer", tags=["production"])
def review_code(files: list[str]) -> str:
    return "Review complete"

# Async works the same way
@trace_agent(name="data-analyst")
async def analyze(query: str) -> dict:
    ...
```

Captures: name, inputs, outputs, duration, success/failure, nested child spans.

### `@trace_llm_call` -- Trace LLM calls with cost estimation

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

Captures: model, token counts, estimated cost (auto-calculated from built-in pricing), latency.

### `Span` -- Instrument any block of code

```python
from agent_watch import Span

with Span("data-preprocessing") as span:
    data = load_data()
    span.set_metadata("rows", len(data))
    cleaned = clean_data(data)
    span.set_output(f"Processed {len(cleaned)} rows")
```

### Automatic nesting

Traces nest automatically. An `@trace_agent` containing `@trace_llm_call` calls produces a parent-child tree:

```python
@trace_agent(name="research-agent")
async def research(topic):
    summary = await search_web(topic)      # child span
    analysis = await analyze(summary)       # child span
    return analysis
```

## CLI

All analytics happen in your terminal. No browser tab required.

### `agent-watch status`

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

```
$ agent-watch traces --agent research-agent --status error
```

### `agent-watch alerts`

```
$ agent-watch alerts

  ! COST SPIKE: Daily cost ($4.21/day) is 2.3x the baseline ($1.83/day)
  ! ERROR SPIKE: code-reviewer success rate dropped from 97.0% to 89.0%
```

## How It Works

All data writes to `.agent-watch/` as append-only JSONL files (one per day). No external services. No network calls. Your prompts and completions never leave your machine.

```
.agent-watch/
  2026-04-07.jsonl
  2026-04-08.jsonl
```

The files are plain JSON Lines. Grep them, pipe them, write scripts against them:

```bash
# Find all runs that cost more than $1
cat .agent-watch/2026-04-08.jsonl | jq 'select(.metadata.cost_usd > 1.0)'
```

### Cost estimation

Built-in pricing for Claude, GPT-4, Gemini, and Llama models. Auto-calculates cost from token counts. Override with your own pricing via `AGENT_WATCH_PRICING` env var pointing to a YAML file.

### Privacy by default

Your data stays local. Period. This makes Agent Watch safe for healthcare, legal, finance, and any environment where prompts and completions cannot leave the machine. No terms of service. No data processing agreements. No risk.

## When to graduate

Agent Watch is designed to be the first tool you install, not the last. When your team grows and you need shared dashboards, RBAC, and real-time alerting, graduate to a platform:

- **Langfuse** (open source, self-hostable)
- **Arize Phoenix** (open source, ML + LLM)
- **Datadog LLM Observability** (enterprise, full-stack)

Your `.agent-watch/` JSONL data is portable. Take it with you.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full feature plan: v0.2 (developer experience), v0.3 (agent intelligence), v0.4 (graduation path to Langfuse/Datadog/OTel), and v1.0 (production ready).

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

## Contributing

```bash
git clone https://github.com/shaan-ad/agent-watch.git
cd agent-watch
pip install -e ".[dev]"
pytest -v
```

## License

MIT

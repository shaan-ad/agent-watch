# Agent Watch Roadmap

## The pivot (April 2026)

Agent Watch launched as "the sqlite of LLM observability." Research into the April 2026 landscape killed that positioning:

- **Langfuse was acquired by ClickHouse in January 2026.** The OSS observability race is effectively over.
- **Arize Phoenix ships polished local mode**, Pydantic Logfire has a trusted brand, OpenLLMetry owns the OTel GenAI spec. "Local JSONL + decorators" is no longer differentiated.
- **The unmet pain is enforcement, not observation.** Every competitor tracks cost. None stop a runaway agent at the decorator layer. The "$47,000 agent loop" post, the "$4,800 bill, nobody knew why" post, and the "$340 loop in an hour" post are canonical 2026 developer pain. Alerts are not enforcement.

v1.0 pivots from "observability on-ramp" to **circuit breaker for runaway agent bills**, with OTel export as the credibility layer that keeps the on-ramp story true.

---

## Positioning

**One-liner:** The circuit breaker your agents don't have. Set a budget. Get a kill-switch. Sleep at night.

**Villain:** Datadog's $120/day LLM premium, and the agent loops that trigger $4K surprise invoices before anyone notices.

**Wedge:** Hard budget enforcement at the decorator. `BudgetExceeded` raised before the next LLM call fires, not after the bill arrives.

**Graduation story (kept, quieter):** When you outgrow local enforcement and want shared dashboards, `agent-watch export --to langfuse` or `--to otlp` and take your data with you. No lock-in.

---

## v0.1.0 (shipped April 9, 2026)

The foundation. Two decorators, local JSONL storage, a CLI.

- [x] `@trace_agent` decorator (sync + async)
- [x] `@trace_llm_call` decorator with auto cost estimation
- [x] `Span` context manager for custom instrumentation
- [x] Automatic parent-child nesting
- [x] JSONL local storage (append-only, one file per day)
- [x] Built-in pricing for Claude, GPT-4, Gemini, Llama
- [x] CLI: `status`, `costs`, `traces`, `report`, `alerts`
- [x] CI pipeline with ruff + pytest

---

## v1.0.0: The Circuit Breaker (target: ~4 weeks from April 16, 2026)

**Goal:** Ship a Show HN that opens with a live demo of an agent burning simulated spend, caught and killed at a $5 cap by Agent Watch. No account. No Docker. One `pip install`.

### 1. Hard budget enforcement

The core wedge. Decorators accept a budget cap. When crossed, the next LLM call raises `BudgetExceeded` instead of firing.

```python
from agent_watch import trace_agent, BudgetExceeded

@trace_agent(name="research", budget_usd=5.00, on_exceed="raise")
async def research(topic: str) -> str:
    ...

try:
    await research("summarize competitor pricing")
except BudgetExceeded as e:
    log.error(f"Killed at ${e.spent_usd:.2f} / ${e.budget_usd:.2f}")
```

- `budget_usd` at decorator level (per-run cap)
- `AGENT_WATCH_BUDGET_USD` env var (per-process cap)
- `on_exceed`: `"raise"` (default) or `"warn"`
- Supports nested agents: child budgets inherit from parent unless overridden
- `agent-watch budgets` CLI shows active caps and spend against them

### 2. OTel-native span format

Rewrite the JSONL schema to match the OpenTelemetry GenAI semantic conventions. Every span Agent Watch writes locally is already OTel-shaped, so export is a transform, not a rewrite.

- Span names, attributes, events aligned to `gen_ai.*` conventions
- Existing CLI commands keep working (read layer unchanged)
- v0.1 JSONL files readable via a migration flag

### 3. One-command exporters

The graduation story made literal.

```bash
agent-watch export --to langfuse --endpoint https://cloud.langfuse.com
agent-watch export --to phoenix --endpoint http://localhost:6006
agent-watch export --to otlp --endpoint http://localhost:4317
agent-watch export --to csv
```

- Langfuse and Phoenix tested end to end against their hosted free tiers
- OTLP export tested against a local collector
- Exports are idempotent (re-running skips already-exported spans)

### 4. `agent-watch diff`

Git-bisect for agent runs. Show the per-step cost delta between two runs of the same agent.

```bash
$ agent-watch diff <run-id-a> <run-id-b>

research-agent (ran 2x)
  step                   run-a    run-b    delta
  ──────────────────────────────────────────────────
  call_claude (query)    $0.12    $0.38    +216%  ← new 3x larger prompt
  call_claude (summary)  $0.08    $0.09    +12%
  TOTAL                  $0.20    $0.47    +135%
```

- Defaults: `agent-watch diff` compares the last two runs of the most recently traced agent
- Works for any two run IDs
- Output mode: terminal table, `--json` for scripting

### 5. `agent-watch replay`

Render a single self-contained HTML file for any run. No server, no dashboard.

```bash
$ agent-watch replay <run-id> --open
# writes ./.agent-watch/replays/<run-id>.html and opens it
```

- Timeline of spans with inputs, outputs, cost, latency
- Interactive filter by span type
- Works offline, embeddable in issue trackers or Slack threads

### 6. Landing page with live demo

`agentwatch.dev` (or similar). One page, one video, one install command.

- 30-second video: agent loop in a terminal, spend climbing, Agent Watch kills it at $5
- Copy-paste install snippet
- Link to Show HN launch post and GitHub
- No signup, no email capture

### 7. Stability commitments

- Public API frozen: no breaking changes to decorators or JSONL schema after v1.0
- Performance: < 1ms overhead per span (benchmarked in CI)
- Docs site at `agentwatch.dev/docs` (MkDocs or similar, shipped with the landing page)
- Published to PyPI with verified publisher

---

## Deliberately not in v1.0

These were in the old roadmap. They are cut or deferred so v1.0 ships.

| Cut / deferred | Reason |
|---|---|
| Inline run summary (`[agent-watch] ...` after every run) | Nice polish, but does not sell the wedge. Add in v1.1 if users ask. |
| `agent-watch watch` live tail | Solves a problem users don't have yet. Defer. |
| Tag-based filtering and A/B compare | Power-user feature. v1.1. |
| JSON output on all CLI commands | Add per-command as needed, not as a theme. |
| Cost-per-goal tracking | Interesting, but `diff` delivers a stronger "aha." Revisit v1.1. |
| Multi-agent correlation tree | OTel export makes this Phoenix's job. Do not rebuild it. |
| Reliability scoring / health command | Secondary to the cost story. v1.2. |
| TypeScript / JS SDK | Huge lift. Post-v1.0 only if Python lands hard. |
| Plugin system for custom exporters | Ship three exporters well before abstracting. |
| CI integration recipe | Documentation, not a feature. Add to docs site. |
| Custom pricing YAML override | Keep the `AGENT_WATCH_PRICING` env var (simple), drop the elaborate schema. |

---

## Post-v1.0 (uncommitted)

If v1.0 lands and users show up, these are the likely next bets in priority order:

1. **Inline run summary** and `watch` live tail (DX polish)
2. **Cost-per-goal tracking** (`@trace_agent(goal="...")`)
3. **CI recipe and pre-commit hook** (fail a PR if test-run cost regresses)
4. **Reliability scoring** (`agent-watch health`)
5. **Adapters for OpenAI Agents SDK, LangGraph, CrewAI** (auto-instrument, no decorators required)
6. **TypeScript SDK** (only if Python adoption justifies it)

Cloud product (shared dashboards, RBAC, SSO) stays out of this repo. If it happens, it happens in a separate private one.

---

## Principles

1. **Enforcement, then observation.** The wedge is stopping the bleeding. Observation is how you prove it worked.
2. **Zero services.** No Docker, no Postgres, no account. One `pip install` and a Python import.
3. **OTel-native at the core.** Every span is OTel-shaped. Exports are transforms, not translations.
4. **The graduation ramp is real or it is not claimed.** Every exporter is tested end to end.
5. **Cut to ship.** v1.0 is the circuit breaker plus credibility. Everything else waits.

---

## Launch plan (for reference, not the roadmap)

- Week 1-2: Budget enforcement + OTel schema migration
- Week 3: Exporters (Langfuse, Phoenix, OTLP) + `diff`
- Week 4: `replay`, landing page, docs site, Show HN
- Show HN title: "Show HN: Agent Watch, a circuit breaker for runaway agent bills (zero-config Python CLI)"

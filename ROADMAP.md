# Agent Watch Roadmap

## Vision

Agent Watch is the first tool every AI agent developer installs. It provides cost, latency, and reliability data from line one of development, with zero setup friction. When teams outgrow local analytics, they graduate to a platform. Agent Watch is the on-ramp, not the destination.

---

## v0.1.0 (Current)

**Status:** Shipped

The foundation. Two decorators, local JSONL storage, and a CLI.

- [x] `@trace_agent` decorator (sync + async)
- [x] `@trace_llm_call` decorator with auto cost estimation
- [x] `Span` context manager for custom instrumentation
- [x] Automatic parent-child nesting
- [x] JSONL local storage (append-only, one file per day)
- [x] Built-in pricing for Claude, GPT-4, Gemini, Llama
- [x] CLI: `status`, `costs`, `traces`, `report`, `alerts`
- [x] CI pipeline with ruff + pytest

---

## v0.2.0 -- Developer Experience

**Goal:** Make agent-watch feel like a native part of the development workflow, not a separate tool.

### Inline run summary
Print a one-liner after every agent run so developers see cost/latency without running CLI commands:
```
[agent-watch] research-agent: $0.12 | 3.4s | 2,847 tokens | OK
```
Configurable via `AGENT_WATCH_QUIET=1` to suppress.

### `agent-watch watch` (live tail)
Real-time stream of agent activity in the terminal. Like `tail -f` for your agents:
```bash
$ agent-watch watch
14:32:01  research-agent    $0.12  3.4s  OK
14:32:05  code-reviewer     $0.08  1.2s  OK
14:32:09  research-agent    $0.31  5.1s  ERROR: context length exceeded
```

### Tag-based filtering
Filter all CLI commands by tags for A/B comparisons:
```bash
agent-watch costs --tag v2-prompt --compare v1-prompt
```

### JSON output mode
Machine-readable output from every CLI command for scripting:
```bash
agent-watch status --json | jq '.total_cost'
```

---

## v0.3.0 -- Agent Intelligence

**Goal:** Go beyond raw metrics. Help developers understand *why* their agents behave the way they do.

### Cost-per-goal tracking
Track cost at the task level, not just the call level. "This research task cost $2.40 across 7 LLM calls" instead of raw token counts:
```python
@trace_agent(name="research", goal="Summarize competitor pricing")
async def research(topic):
    ...
```
```bash
$ agent-watch costs --by goal
  "Summarize competitor pricing"    $2.40  (7 calls, 3 retries)
  "Generate weekly report"          $0.89  (4 calls, 0 retries)
```

### Multi-agent correlation
Trace execution across agent boundaries. When agent A calls agent B which calls agent C, see the full chain:
```bash
$ agent-watch traces --trace-id abc123 --tree
  orchestrator        $1.20  4.2s  OK
    research-agent    $0.80  3.1s  OK
      call_claude     $0.45  1.8s  OK
      call_claude     $0.35  1.3s  OK
    summarizer        $0.40  1.1s  OK
      call_gpt4o      $0.40  1.1s  OK
```

### Reliability scoring
Track success rate trends with anomaly detection. Surface degradation before it becomes a problem:
```bash
$ agent-watch health
  research-agent     97.2% (7d avg)  stable
  code-reviewer      84.1% (7d avg)  DEGRADING (was 96.3% last week)
  summarizer         99.8% (7d avg)  stable
```

### Cost threshold alerts
Set budget guardrails. Get warned in the terminal if a single run exceeds a threshold:
```python
@trace_agent(name="research", cost_limit=5.00)
async def research(topic):
    ...
```
```
[agent-watch] WARNING: research-agent run exceeded $5.00 limit ($6.12)
```

---

## v0.4.0 -- Graduation Path

**Goal:** Make it seamless to move from local analytics to a team platform when you're ready.

### OpenTelemetry export
Export traces as OTel spans to any compatible backend:
```bash
agent-watch export --format otlp --endpoint https://your-collector:4317
```

### Platform-specific export
One-command export to popular platforms:
```bash
agent-watch export --format langfuse --endpoint https://cloud.langfuse.com
agent-watch export --format datadog
agent-watch export --format csv
```

### CI integration
Run agent-watch checks in CI to catch cost/reliability regressions before merge:
```yaml
# .github/workflows/agent-check.yml
- name: Check agent costs
  run: |
    agent-watch report --days 1 --format json | \
    jq -e '.total_cost < 10.0' || exit 1
```

### Custom pricing overrides
Load organization-specific pricing (negotiated rates, fine-tuned model costs):
```bash
export AGENT_WATCH_PRICING=./pricing.yaml
```

---

## v1.0.0 -- Production Ready

**Goal:** Stable, documented, trusted by teams in production.

- [ ] Stable API (no breaking changes to decorators or JSONL schema)
- [ ] Comprehensive docs site
- [ ] TypeScript/JavaScript SDK (second language)
- [ ] Plugin system for custom exporters
- [ ] Benchmark suite (performance overhead < 1ms per span)
- [ ] Published to PyPI with verified publisher

---

## Future (Cloud, separate repo)

Not part of the open-source CLI. These are team/enterprise features that require a server component:

- Shared dashboard with team visibility
- Role-based access control
- Real-time alerting (Slack, email, PagerDuty)
- Historical data retention and aggregation
- SSO/SAML for enterprise
- SOC 2 compliance

The cloud product will be built in a separate private repository. The open-source CLI remains the on-ramp and the local development experience.

---

## Principles

1. **Zero friction beats features.** If a feature requires config, an account, or a browser tab, think twice.
2. **CLI first.** Every feature works from the terminal. A dashboard is a future add-on, not the product.
3. **Local by default.** Data stays on the developer's machine unless they explicitly export it.
4. **Framework agnostic.** Works with LangChain, CrewAI, AutoGen, LangGraph, bare Python, or anything else.
5. **Complement, don't compete.** Agent Watch is the on-ramp to Langfuse/Datadog/Arize, not a replacement.

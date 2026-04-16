# Agent Watch v1.0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Agent Watch from its v0.1 custom span schema to an OpenTelemetry GenAI-aligned schema, and add hard budget enforcement (the v1.0 wedge feature: `BudgetExceeded` raised in-flight when an agent crosses its USD cap).

**Architecture:**
1. **Schema**: Rename `Event` to `Span`. Align field names and attribute keys with OpenTelemetry GenAI semantic conventions (`gen_ai.*`). Do not add the OTel SDK as a dependency — we shape our JSONL to match OTel, and exporters (Plan 2) convert to OTLP. Keep backward-compat for reading v0.1 JSONL via a `schema` version field.
2. **Budget**: New `Budget` class + `BudgetExceeded` exception. Budgets are tracked per contextvar (parent-scoped, like `parent_id`). Enforcement point is the end of each traced LLM call: after computing cost, if cumulative spend in the active budget context exceeds the cap, raise. That stops the next call in the loop from firing.

**Tech Stack:** Python 3.9+, dataclasses, contextvars, pytest, pytest-asyncio, ruff. No new runtime dependencies.

**Non-goals for this plan:**
- Exporters (Plan 2)
- `diff` / `replay` CLI commands (Plan 3)
- Landing page, docs site, Show HN (Plan 4)
- OTel SDK integration (we use OTel *semantic conventions*, not the SDK, to keep the tool dependency-free)

---

## File Structure

**Create:**
- `src/agent_watch/otel.py` — OTel GenAI attribute constants (single source of truth for attribute keys)
- `src/agent_watch/budget.py` — `Budget` class, `BudgetExceeded` exception, budget contextvars
- `tests/test_otel_schema.py` — schema-level tests (serialization, backward compat)
- `tests/test_budget.py` — budget enforcement tests

**Modify:**
- `src/agent_watch/types.py` — rename `Event` → `Span`, add `trace_id`, rename `id`→`span_id`, `parent_id`→`parent_span_id`, `metadata`→`attributes`, add `schema` field
- `src/agent_watch/collector.py` — rename contextvars, add trace_id management, add backward-compat reader
- `src/agent_watch/decorators.py` — write OTel-shaped attributes, wire budget enforcement
- `src/agent_watch/span.py` — rename internal `Event` references to `Span`
- `src/agent_watch/storage.py` — read both v0.1 and v1 JSONL, update aggregations to read `attributes` with `gen_ai.*` keys
- `src/agent_watch/__init__.py` — export `Span` (the new type), keep `Event` as a deprecation alias
- `src/agent_watch/cli/*.py` — update any code that reads `metadata["model"]`, `metadata["cost_usd"]`, etc. to use the new attribute keys
- `tests/conftest.py` — update `sample_events` fixture to new schema
- `tests/test_decorators.py`, `tests/test_collector.py`, `tests/test_span.py`, `tests/test_storage.py`, `tests/test_cli_*.py` — update assertions to new field names

**Delete:** None.

---

## Schema Mapping Reference

Keep this next to you while implementing. Every code change reads or writes one of these fields.

| v0.1 field/key | v1.0 field/key | Notes |
|---|---|---|
| `Event` (class name) | `Span` | `Event` kept as deprecated alias in `__init__.py` |
| `event.id` | `span.span_id` | UUID4, unchanged generation |
| (new) | `span.trace_id` | UUID4, shared across all spans in one top-level agent run |
| `event.parent_id` | `span.parent_span_id` | |
| `event.type` | `span.kind` | Values: `"agent"`, `"llm"`, `"span"` (was `"agent_run"`, `"llm_call"`, `"span"`) |
| `event.metadata` | `span.attributes` | |
| `event.metadata["model"]` | `span.attributes["gen_ai.request.model"]` | |
| `event.metadata["input_tokens"]` | `span.attributes["gen_ai.usage.input_tokens"]` | |
| `event.metadata["output_tokens"]` | `span.attributes["gen_ai.usage.output_tokens"]` | |
| `event.metadata["cost_usd"]` | `span.attributes["agent_watch.cost_usd"]` | Not standardized in OTel, keep under our namespace |
| `event.metadata["tags"]` | `span.attributes["agent_watch.tags"]` | Same reasoning |
| `event.status` = `"success"` | `span.status` = `"ok"` | OTel StatusCode naming, lowercased |
| `event.status` = `"error"` | `span.status` = `"error"` | Unchanged |
| (new) | `span.schema` = `"agent-watch/v1"` | Version tag in every JSONL line |

---

## Phase 1: OTel Schema Migration

### Task 1: Create v1.0-foundation branch

**Files:** repo working tree

- [ ] **Step 1: Create branch**

Run: `cd /Users/agaras/agent-watch && git checkout -b v1.0-foundation`
Expected: `Switched to a new branch 'v1.0-foundation'`

- [ ] **Step 2: Verify clean start**

Run: `git status`
Expected: `working tree clean`

---

### Task 2: Create OTel attribute constants module

**Files:**
- Create: `src/agent_watch/otel.py`
- Test: `tests/test_otel_schema.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_otel_schema.py`:

```python
"""Tests for OTel attribute constants and schema mapping."""

from agent_watch import otel


def test_gen_ai_attribute_constants_exist():
    assert otel.GEN_AI_REQUEST_MODEL == "gen_ai.request.model"
    assert otel.GEN_AI_USAGE_INPUT_TOKENS == "gen_ai.usage.input_tokens"
    assert otel.GEN_AI_USAGE_OUTPUT_TOKENS == "gen_ai.usage.output_tokens"
    assert otel.GEN_AI_SYSTEM == "gen_ai.system"
    assert otel.GEN_AI_OPERATION_NAME == "gen_ai.operation.name"


def test_agent_watch_namespaced_constants_exist():
    assert otel.AGENT_WATCH_COST_USD == "agent_watch.cost_usd"
    assert otel.AGENT_WATCH_TAGS == "agent_watch.tags"


def test_schema_version_constant():
    assert otel.SCHEMA_VERSION == "agent-watch/v1"


def test_span_kind_constants():
    assert otel.KIND_AGENT == "agent"
    assert otel.KIND_LLM == "llm"
    assert otel.KIND_SPAN == "span"


def test_status_constants():
    assert otel.STATUS_OK == "ok"
    assert otel.STATUS_ERROR == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/agaras/agent-watch && pytest tests/test_otel_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_watch.otel'`

- [ ] **Step 3: Implement the module**

Create `src/agent_watch/otel.py`:

```python
"""OpenTelemetry GenAI semantic convention constants and Agent Watch namespaced keys.

This module is the single source of truth for attribute key names. Decorators,
collectors, readers, and exporters all reference these constants.

References:
- OTel GenAI conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
"""

# --- OTel GenAI standard attribute keys ---
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_AGENT_ID = "gen_ai.agent.id"

# --- Agent Watch namespaced keys (not in OTel spec) ---
AGENT_WATCH_COST_USD = "agent_watch.cost_usd"
AGENT_WATCH_TAGS = "agent_watch.tags"
AGENT_WATCH_BUDGET_USD = "agent_watch.budget_usd"
AGENT_WATCH_BUDGET_EXCEEDED = "agent_watch.budget_exceeded"

# --- Schema version ---
SCHEMA_VERSION = "agent-watch/v1"

# --- Span kinds (Agent Watch-specific taxonomy) ---
KIND_AGENT = "agent"
KIND_LLM = "llm"
KIND_SPAN = "span"

# --- Status values (aligned with OTel StatusCode lowercased) ---
STATUS_OK = "ok"
STATUS_ERROR = "error"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_otel_schema.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_watch/otel.py tests/test_otel_schema.py
git commit -m "feat: add OTel GenAI attribute constants module"
```

---

### Task 3: Rename Event to Span, add v1 fields, backward-compat read

**Files:**
- Modify: `src/agent_watch/types.py`
- Test: `tests/test_otel_schema.py` (extend existing file)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_otel_schema.py`:

```python
from agent_watch.types import Span, make_agent_span, make_llm_span, make_generic_span
from agent_watch import otel


def test_span_has_v1_fields():
    s = Span(name="test")
    assert hasattr(s, "span_id")
    assert hasattr(s, "trace_id")
    assert hasattr(s, "parent_span_id")
    assert hasattr(s, "kind")
    assert hasattr(s, "attributes")
    assert hasattr(s, "schema")
    assert s.schema == otel.SCHEMA_VERSION


def test_span_defaults():
    s = Span(name="x")
    assert s.span_id  # non-empty UUID
    assert s.trace_id  # non-empty UUID
    assert s.parent_span_id is None
    assert s.kind == otel.KIND_SPAN
    assert s.status == otel.STATUS_OK
    assert s.attributes == {}
    assert s.schema == otel.SCHEMA_VERSION


def test_span_serialization_roundtrip():
    s = Span(name="agent-x", kind=otel.KIND_AGENT)
    s.attributes[otel.GEN_AI_REQUEST_MODEL] = "gpt-4o"
    s.attributes[otel.AGENT_WATCH_COST_USD] = 0.123
    line = s.to_json()
    parsed = Span.from_json(line)
    assert parsed.span_id == s.span_id
    assert parsed.trace_id == s.trace_id
    assert parsed.kind == otel.KIND_AGENT
    assert parsed.attributes[otel.GEN_AI_REQUEST_MODEL] == "gpt-4o"
    assert parsed.attributes[otel.AGENT_WATCH_COST_USD] == 0.123
    assert parsed.schema == otel.SCHEMA_VERSION


def test_span_from_json_reads_v01_legacy_format():
    # An old v0.1 JSONL line uses 'id', 'type', 'parent_id', 'metadata'
    legacy = (
        '{"id": "old-1", "type": "agent_run", "name": "legacy-agent", '
        '"parent_id": null, "start_time": 100.0, "end_time": 101.0, '
        '"duration_ms": 1000.0, "status": "success", "error": null, '
        '"input_preview": "q", "output_preview": "a", '
        '"metadata": {"model": "gpt-4", "cost_usd": 0.5, "tags": ["x"]}, '
        '"children": []}'
    )
    s = Span.from_json(legacy)
    assert s.span_id == "old-1"
    assert s.kind == otel.KIND_AGENT  # agent_run -> agent
    assert s.parent_span_id is None
    assert s.status == otel.STATUS_OK  # success -> ok
    assert s.attributes[otel.GEN_AI_REQUEST_MODEL] == "gpt-4"
    assert s.attributes[otel.AGENT_WATCH_COST_USD] == 0.5
    assert s.attributes[otel.AGENT_WATCH_TAGS] == ["x"]
    # Legacy spans get a synthetic trace_id equal to their span_id
    assert s.trace_id == "old-1"


def test_make_agent_span_sets_kind():
    s = make_agent_span("research", tags=["prod"])
    assert s.kind == otel.KIND_AGENT
    assert s.name == "research"
    assert s.attributes[otel.AGENT_WATCH_TAGS] == ["prod"]


def test_make_llm_span_sets_kind_and_model():
    s = make_llm_span("call_claude", model="claude-sonnet-4-20250514")
    assert s.kind == otel.KIND_LLM
    assert s.name == "call_claude"
    assert s.attributes[otel.GEN_AI_REQUEST_MODEL] == "claude-sonnet-4-20250514"


def test_make_generic_span_sets_kind():
    s = make_generic_span("preprocessing")
    assert s.kind == otel.KIND_SPAN
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_otel_schema.py -v`
Expected: the new 7 tests FAIL (import errors, missing fields)

- [ ] **Step 3: Rewrite `src/agent_watch/types.py`**

Replace the entire contents of `src/agent_watch/types.py` with:

```python
"""Span types for agent telemetry, aligned with OpenTelemetry GenAI conventions."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from agent_watch import otel


@dataclass
class Span:
    """Telemetry span, OTel GenAI-aligned.

    Attributes use OTel semantic convention keys (see ``agent_watch.otel``).
    Serialization emits a ``schema`` field so readers can detect format.
    """

    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: Optional[str] = None
    kind: str = otel.KIND_SPAN
    name: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    duration_ms: float = 0.0
    status: str = otel.STATUS_OK
    error: Optional[str] = None
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)
    schema: str = otel.SCHEMA_VERSION

    def finish(self, status: str = otel.STATUS_OK, error: Optional[str] = None) -> None:
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status
        if error:
            self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Span:
        if "schema" in data and data["schema"] == otel.SCHEMA_VERSION:
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        return _from_legacy_v01(data)

    @classmethod
    def from_json(cls, line: str) -> Span:
        return cls.from_dict(json.loads(line))


# Deprecated alias for v0.1 compatibility. Will be removed in v2.0.
Event = Span


_LEGACY_TYPE_TO_KIND = {
    "agent_run": otel.KIND_AGENT,
    "llm_call": otel.KIND_LLM,
    "span": otel.KIND_SPAN,
}

_LEGACY_STATUS = {
    "success": otel.STATUS_OK,
    "error": otel.STATUS_ERROR,
}

_LEGACY_METADATA_REMAP = {
    "model": otel.GEN_AI_REQUEST_MODEL,
    "input_tokens": otel.GEN_AI_USAGE_INPUT_TOKENS,
    "output_tokens": otel.GEN_AI_USAGE_OUTPUT_TOKENS,
    "cost_usd": otel.AGENT_WATCH_COST_USD,
    "tags": otel.AGENT_WATCH_TAGS,
}


def _from_legacy_v01(data: Dict[str, Any]) -> Span:
    """Translate a v0.1 Event dict into a v1.0 Span."""
    legacy_metadata = data.get("metadata", {}) or {}
    attributes: Dict[str, Any] = {}
    for legacy_key, value in legacy_metadata.items():
        attributes[_LEGACY_METADATA_REMAP.get(legacy_key, legacy_key)] = value

    legacy_id = data.get("id", "")
    return Span(
        span_id=legacy_id,
        trace_id=legacy_id,  # synthesize: legacy spans are their own trace root
        parent_span_id=data.get("parent_id"),
        kind=_LEGACY_TYPE_TO_KIND.get(data.get("type", "span"), otel.KIND_SPAN),
        name=data.get("name", ""),
        start_time=data.get("start_time", 0.0),
        end_time=data.get("end_time", 0.0),
        duration_ms=data.get("duration_ms", 0.0),
        status=_LEGACY_STATUS.get(data.get("status", "success"), otel.STATUS_OK),
        error=data.get("error"),
        input_preview=data.get("input_preview"),
        output_preview=data.get("output_preview"),
        attributes=attributes,
        children=list(data.get("children", []) or []),
        schema=otel.SCHEMA_VERSION,
    )


def make_agent_span(
    name: str,
    parent_span_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Span:
    """Create an agent-kind span."""
    span = Span(kind=otel.KIND_AGENT, name=name, parent_span_id=parent_span_id)
    if trace_id:
        span.trace_id = trace_id
    if tags:
        span.attributes[otel.AGENT_WATCH_TAGS] = tags
    return span


def make_llm_span(
    name: str,
    model: str,
    parent_span_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Span:
    """Create an llm-kind span."""
    span = Span(kind=otel.KIND_LLM, name=name, parent_span_id=parent_span_id)
    if trace_id:
        span.trace_id = trace_id
    if model:
        span.attributes[otel.GEN_AI_REQUEST_MODEL] = model
    return span


def make_generic_span(
    name: str,
    parent_span_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Span:
    """Create a generic span."""
    span = Span(kind=otel.KIND_SPAN, name=name, parent_span_id=parent_span_id)
    if trace_id:
        span.trace_id = trace_id
    return span


# --- Legacy helper aliases (for any code still using v0.1 names) ---
make_agent_event = make_agent_span
make_llm_event = make_llm_span
make_span_event = make_generic_span


def preview(value: Any, max_len: int = 200) -> Optional[str]:
    """Create a preview string from any value."""
    if value is None:
        return None
    s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_otel_schema.py -v`
Expected: all tests in file PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_watch/types.py tests/test_otel_schema.py
git commit -m "feat(schema): rename Event to Span, add OTel-aligned fields and legacy reader"
```

---

### Task 4: Update collector to use Span + add trace_id propagation

**Files:**
- Modify: `src/agent_watch/collector.py`
- Test: `tests/test_collector.py`

- [ ] **Step 1: Read current `test_collector.py` for context**

Run: `cat tests/test_collector.py`
Expected: existing tests using `Event`, `metadata`, etc.

- [ ] **Step 2: Write a failing test for trace_id propagation**

Append to `tests/test_collector.py`:

```python
def test_get_current_trace_id_default_is_none():
    from agent_watch.collector import get_current_trace_id
    assert get_current_trace_id() is None


def test_set_current_trace_id_returns_previous():
    from agent_watch.collector import get_current_trace_id, set_current_trace_id
    prev = set_current_trace_id("trace-abc")
    assert get_current_trace_id() == "trace-abc"
    assert prev is None
    prev2 = set_current_trace_id(None)
    assert prev2 == "trace-abc"
    assert get_current_trace_id() is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_collector.py::test_get_current_trace_id_default_is_none -v`
Expected: FAIL with ImportError

- [ ] **Step 4: Update `src/agent_watch/collector.py`**

Replace the entire contents with:

```python
"""Span collector: captures spans and writes to JSONL files."""

from __future__ import annotations

import contextvars
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from agent_watch.types import Span

# Context variables for span tracking (threads + async safe)
_parent_span_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "agent_watch_parent_span_id", default=None
)
_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "agent_watch_trace_id", default=None
)
_children_var: contextvars.ContextVar[Dict[str, List[str]]] = contextvars.ContextVar(
    "agent_watch_children", default={}
)

# Legacy aliases so external code (and conftest fixture reset) keeps working
_parent_id_var = _parent_span_id_var

DEFAULT_DIR = ".agent-watch"


def get_storage_dir() -> Path:
    dir_path = Path(os.environ.get("AGENT_WATCH_DIR", DEFAULT_DIR))
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_today_file() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return get_storage_dir() / f"{today}.jsonl"


def write_span(span: Span) -> None:
    """Append a span to today's JSONL file."""
    filepath = get_today_file()
    line = span.to_json() + "\n"
    with open(filepath, "a") as f:
        f.write(line)


# Deprecated alias
write_event = write_span


def get_current_parent_id() -> Optional[str]:
    return _parent_span_id_var.get()


def set_current_parent_id(parent_id: Optional[str]) -> Optional[str]:
    previous = _parent_span_id_var.get()
    _parent_span_id_var.set(parent_id)
    return previous


def get_current_trace_id() -> Optional[str]:
    return _trace_id_var.get()


def set_current_trace_id(trace_id: Optional[str]) -> Optional[str]:
    previous = _trace_id_var.get()
    _trace_id_var.set(trace_id)
    return previous


def add_child_to_parent(parent_id: str, child_id: str) -> None:
    children = _children_var.get()
    if parent_id not in children:
        children = {**children, parent_id: []}
    else:
        children = {**children, parent_id: list(children[parent_id])}
    children[parent_id].append(child_id)
    _children_var.set(children)


def get_children(parent_id: str) -> List[str]:
    children = _children_var.get()
    return children.get(parent_id, [])
```

- [ ] **Step 5: Update `tests/conftest.py` to reset the new contextvar**

Edit `tests/conftest.py`, inside the `temp_storage` fixture, after the existing `collector._children_var.set({})` line, add:

```python
    collector._trace_id_var.set(None)
```

- [ ] **Step 6: Run collector tests to verify**

Run: `pytest tests/test_collector.py -v`
Expected: all tests PASS (existing tests should still work because `write_event` is aliased to `write_span`)

- [ ] **Step 7: Commit**

```bash
git add src/agent_watch/collector.py tests/test_collector.py tests/conftest.py
git commit -m "feat(collector): rename to Span, add trace_id contextvar"
```

---

### Task 5: Update decorators to write OTel-shaped spans with trace_id

**Files:**
- Modify: `src/agent_watch/decorators.py`
- Test: `tests/test_decorators.py`

- [ ] **Step 1: Write failing tests for new field names**

Append to `tests/test_decorators.py`:

```python
from agent_watch import otel


def test_trace_agent_uses_v1_schema(temp_storage):
    @trace_agent(name="schema-agent")
    def my_agent():
        return "ok"

    my_agent()
    events = _read_events(temp_storage)
    assert events[0]["schema"] == otel.SCHEMA_VERSION
    assert events[0]["kind"] == otel.KIND_AGENT
    assert events[0]["status"] == otel.STATUS_OK
    assert "span_id" in events[0]
    assert "trace_id" in events[0]


def test_trace_agent_tags_in_attributes(temp_storage):
    @trace_agent(name="tagged", tags=["prod", "v2"])
    def a():
        return "ok"

    a()
    events = _read_events(temp_storage)
    assert events[0]["attributes"][otel.AGENT_WATCH_TAGS] == ["prod", "v2"]


def test_trace_llm_call_uses_gen_ai_attributes(temp_storage):
    @trace_llm_call(model="gpt-4o")
    def call(prompt: str) -> dict:
        return {"content": "x", "input_tokens": 100, "output_tokens": 50}

    call("hi")
    events = _read_events(temp_storage)
    assert events[0]["attributes"][otel.GEN_AI_REQUEST_MODEL] == "gpt-4o"
    assert events[0]["attributes"][otel.GEN_AI_USAGE_INPUT_TOKENS] == 100
    assert events[0]["attributes"][otel.GEN_AI_USAGE_OUTPUT_TOKENS] == 50
    assert events[0]["attributes"][otel.AGENT_WATCH_COST_USD] > 0


def test_nested_traces_share_trace_id(temp_storage):
    import asyncio

    @trace_llm_call(model="gpt-4o")
    async def inner(p: str) -> dict:
        return {"content": "x", "input_tokens": 10, "output_tokens": 5}

    @trace_agent(name="outer")
    async def outer(q: str) -> str:
        r = await inner(q)
        return r["content"]

    asyncio.run(outer("hi"))
    events = _read_events(temp_storage)
    trace_ids = {e["trace_id"] for e in events}
    assert len(trace_ids) == 1
```

- [ ] **Step 2: Run tests to see failures**

Run: `pytest tests/test_decorators.py -v`
Expected: several FAILs

- [ ] **Step 3: Rewrite `src/agent_watch/decorators.py`**

Replace the entire contents of `src/agent_watch/decorators.py` with:

```python
"""Decorators for tracing agent functions and LLM calls."""

from __future__ import annotations

import functools
import inspect
import uuid
from typing import Any, Callable, List, Optional

from agent_watch import otel
from agent_watch.collector import (
    add_child_to_parent,
    get_children,
    get_current_parent_id,
    get_current_trace_id,
    set_current_parent_id,
    set_current_trace_id,
    write_span,
)
from agent_watch.cost import estimate_cost
from agent_watch.types import Span, make_agent_span, make_llm_span, preview


def trace_agent(
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Callable:
    """Trace an agent function (sync or async)."""

    def decorator(func: Callable) -> Callable:
        agent_name = name or func.__name__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                return await _run_agent_async(func, agent_name, tags, args, kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return _run_agent_sync(func, agent_name, tags, args, kwargs)

        return sync_wrapper

    return decorator


def trace_llm_call(
    model: str = "",
    name: Optional[str] = None,
) -> Callable:
    """Trace an LLM call. Decorated function returns a dict with content/input_tokens/output_tokens."""

    def decorator(func: Callable) -> Callable:
        call_name = name or func.__name__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                return await _run_llm_async(func, call_name, model, args, kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return _run_llm_sync(func, call_name, model, args, kwargs)

        return sync_wrapper

    return decorator


# --- internal helpers ---

def _start_agent_span(agent_name: str, tags: Optional[List[str]]) -> tuple[Span, Optional[str], Optional[str]]:
    parent_id = get_current_parent_id()
    trace_id = get_current_trace_id() or str(uuid.uuid4())
    span = make_agent_span(agent_name, parent_span_id=parent_id, trace_id=trace_id, tags=tags)
    if parent_id:
        add_child_to_parent(parent_id, span.span_id)
    previous_parent = set_current_parent_id(span.span_id)
    previous_trace = set_current_trace_id(trace_id)
    return span, previous_parent, previous_trace


def _start_llm_span(call_name: str, model: str) -> tuple[Span, Optional[str], Optional[str]]:
    parent_id = get_current_parent_id()
    trace_id = get_current_trace_id() or str(uuid.uuid4())
    span = make_llm_span(call_name, model=model, parent_span_id=parent_id, trace_id=trace_id)
    if parent_id:
        add_child_to_parent(parent_id, span.span_id)
    previous_parent = set_current_parent_id(span.span_id)
    previous_trace = set_current_trace_id(trace_id)
    return span, previous_parent, previous_trace


def _finish_span(
    span: Span,
    previous_parent: Optional[str],
    previous_trace: Optional[str],
    status: str,
    error: Optional[str],
) -> None:
    span.children = get_children(span.span_id)
    span.finish(status=status, error=error)
    write_span(span)
    set_current_parent_id(previous_parent)
    set_current_trace_id(previous_trace)


async def _run_agent_async(func: Callable, agent_name: str, tags, args, kwargs) -> Any:
    span, prev_parent, prev_trace = _start_agent_span(agent_name, tags)
    span.input_preview = preview(_format_args(args, kwargs))
    try:
        result = await func(*args, **kwargs)
        span.output_preview = preview(result)
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_OK, None)
        return result
    except Exception as e:
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise


def _run_agent_sync(func: Callable, agent_name: str, tags, args, kwargs) -> Any:
    span, prev_parent, prev_trace = _start_agent_span(agent_name, tags)
    span.input_preview = preview(_format_args(args, kwargs))
    try:
        result = func(*args, **kwargs)
        span.output_preview = preview(result)
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_OK, None)
        return result
    except Exception as e:
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise


async def _run_llm_async(func: Callable, call_name: str, model: str, args, kwargs) -> Any:
    span, prev_parent, prev_trace = _start_llm_span(call_name, model)
    span.input_preview = preview(_format_args(args, kwargs))
    try:
        result = await func(*args, **kwargs)
        _extract_llm_attributes(span, result, model)
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_OK, None)
        return result
    except Exception as e:
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise


def _run_llm_sync(func: Callable, call_name: str, model: str, args, kwargs) -> Any:
    span, prev_parent, prev_trace = _start_llm_span(call_name, model)
    span.input_preview = preview(_format_args(args, kwargs))
    try:
        result = func(*args, **kwargs)
        _extract_llm_attributes(span, result, model)
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_OK, None)
        return result
    except Exception as e:
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise


def _extract_llm_attributes(span: Span, result: Any, model: str) -> None:
    input_tokens = 0
    output_tokens = 0
    content = ""

    if isinstance(result, dict):
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        content = result.get("content", "")
    elif hasattr(result, "input_tokens"):
        input_tokens = getattr(result, "input_tokens", 0)
        output_tokens = getattr(result, "output_tokens", 0)
        content = getattr(result, "content", "")
    elif isinstance(result, str):
        content = result

    span.attributes[otel.GEN_AI_USAGE_INPUT_TOKENS] = input_tokens
    span.attributes[otel.GEN_AI_USAGE_OUTPUT_TOKENS] = output_tokens
    span.output_preview = preview(content)

    if model and (input_tokens or output_tokens):
        cost = estimate_cost(model, input_tokens, output_tokens)
        if cost is not None:
            span.attributes[otel.AGENT_WATCH_COST_USD] = cost


def _format_args(args: tuple, kwargs: dict) -> str:
    parts = [str(a) for a in args]
    parts.extend(f"{k}={v}" for k, v in kwargs.items())
    return ", ".join(parts)
```

- [ ] **Step 4: Update existing decorator tests that check old field names**

In `tests/test_decorators.py`, update assertions that read old fields. Specifically:

Replace every `events[0]["type"] == "agent_run"` with `events[0]["kind"] == otel.KIND_AGENT`.
Replace every `events[0]["type"] == "llm_call"` with `events[0]["kind"] == otel.KIND_LLM`.
Replace every `events[0]["status"] == "success"` with `events[0]["status"] == otel.STATUS_OK`.
Replace every `events[0]["metadata"]["model"]` with `events[0]["attributes"][otel.GEN_AI_REQUEST_MODEL]`.
Replace every `events[0]["metadata"]["input_tokens"]` with `events[0]["attributes"][otel.GEN_AI_USAGE_INPUT_TOKENS]`.
Replace every `events[0]["metadata"]["output_tokens"]` with `events[0]["attributes"][otel.GEN_AI_USAGE_OUTPUT_TOKENS]`.
Replace every `events[0]["metadata"]["cost_usd"]` with `events[0]["attributes"][otel.AGENT_WATCH_COST_USD]`.
Replace every `events[0]["metadata"]["tags"]` with `events[0]["attributes"][otel.AGENT_WATCH_TAGS]`.
In `test_nested_traces`, replace `e["type"] == "agent_run"` with `e["kind"] == otel.KIND_AGENT` and `e["type"] == "llm_call"` with `e["kind"] == otel.KIND_LLM`. Replace `llm_event["parent_id"]` with `llm_event["parent_span_id"]` and `llm_event["id"]` with `llm_event["span_id"]`.

Ensure `from agent_watch import otel` is at the top of the file.

- [ ] **Step 5: Run decorator tests**

Run: `pytest tests/test_decorators.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/agent_watch/decorators.py tests/test_decorators.py
git commit -m "feat(decorators): emit OTel-shaped spans with trace_id propagation"
```

---

### Task 6: Update Span context manager

**Files:**
- Modify: `src/agent_watch/span.py`
- Test: `tests/test_span.py`

- [ ] **Step 1: Read `tests/test_span.py`**

Run: `cat tests/test_span.py`

- [ ] **Step 2: Update `src/agent_watch/span.py`**

Replace the entire contents with:

```python
"""Span context manager for custom instrumentation.

Note: the context manager class is ``Span`` (this file). The telemetry
dataclass is also named ``Span`` but lives in ``agent_watch.types``. We
alias the dataclass as ``_SpanRecord`` here to avoid name collision at
the module level.
"""

from __future__ import annotations

import uuid
from typing import Any, List, Optional

from agent_watch import otel
from agent_watch.collector import (
    add_child_to_parent,
    get_children,
    get_current_parent_id,
    get_current_trace_id,
    set_current_parent_id,
    set_current_trace_id,
    write_span,
)
from agent_watch.types import Span as _SpanRecord
from agent_watch.types import make_generic_span, preview


class Span:
    """Context manager for instrumenting any block of code.

    Usage:
        with Span("data-processing") as span:
            result = process_data(data)
            span.set_metadata("rows", len(data))
    """

    def __init__(
        self,
        name: str,
        tags: Optional[List[str]] = None,
    ):
        self.name = name
        self.tags = tags
        self._span: Optional[_SpanRecord] = None
        self._previous_parent: Optional[str] = None
        self._previous_trace: Optional[str] = None

    def _start(self) -> "Span":
        parent_id = get_current_parent_id()
        trace_id = get_current_trace_id() or str(uuid.uuid4())
        self._span = make_generic_span(name=self.name, parent_span_id=parent_id, trace_id=trace_id)
        if self.tags:
            self._span.attributes[otel.AGENT_WATCH_TAGS] = self.tags
        self._previous_parent = set_current_parent_id(self._span.span_id)
        self._previous_trace = set_current_trace_id(trace_id)
        if parent_id:
            add_child_to_parent(parent_id, self._span.span_id)
        return self

    def _finish(self, error: Optional[str] = None) -> None:
        if self._span is None:
            return
        status = otel.STATUS_ERROR if error else otel.STATUS_OK
        self._span.children = get_children(self._span.span_id)
        self._span.finish(status=status, error=error)
        write_span(self._span)
        set_current_parent_id(self._previous_parent)
        set_current_trace_id(self._previous_trace)

    def set_metadata(self, key: str, value: Any) -> None:
        """Add an attribute to this span (named set_metadata for v0.1 API compat)."""
        if self._span:
            self._span.attributes[key] = value

    def set_attribute(self, key: str, value: Any) -> None:
        """Add an attribute to this span."""
        self.set_metadata(key, value)

    def set_input(self, value: Any) -> None:
        if self._span:
            self._span.input_preview = preview(value)

    def set_output(self, value: Any) -> None:
        if self._span:
            self._span.output_preview = preview(value)

    @property
    def span_id(self) -> Optional[str]:
        return self._span.span_id if self._span else None

    @property
    def event_id(self) -> Optional[str]:
        """Deprecated: use span_id."""
        return self.span_id

    def __enter__(self) -> "Span":
        return self._start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        error = str(exc_val) if exc_val else None
        self._finish(error=error)

    async def __aenter__(self) -> "Span":
        return self._start()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        error = str(exc_val) if exc_val else None
        self._finish(error=error)
```

- [ ] **Step 3: Update `tests/test_span.py` assertions**

Apply the same field-name replacements in `tests/test_span.py` as Task 5 Step 4 (type→kind, metadata→attributes, parent_id→parent_span_id, id→span_id, success→ok). Ensure `from agent_watch import otel` is imported at the top.

- [ ] **Step 4: Run span tests**

Run: `pytest tests/test_span.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_watch/span.py tests/test_span.py
git commit -m "feat(span): update context manager to v1 schema"
```

---

### Task 7: Update storage read path and aggregations

**Files:**
- Modify: `src/agent_watch/storage.py`
- Test: `tests/test_storage.py`, `tests/conftest.py`

- [ ] **Step 1: Update `tests/conftest.py` sample_events fixture to new schema**

Replace the body of the `sample_events` fixture in `tests/conftest.py` with:

```python
@pytest.fixture
def sample_events(temp_storage) -> List[Span]:
    """Write sample spans to storage and return them."""
    import time
    from agent_watch import otel
    from agent_watch.types import Span

    now = time.time()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filepath = temp_storage / f"{today}.jsonl"

    spans = [
        Span(
            span_id="evt-1",
            trace_id="evt-1",
            kind=otel.KIND_AGENT,
            name="research-agent",
            start_time=now - 100,
            end_time=now - 98,
            duration_ms=2000.0,
            status=otel.STATUS_OK,
            input_preview="quantum computing",
            output_preview="Summary of quantum computing...",
            attributes={
                otel.AGENT_WATCH_TAGS: ["test"],
                otel.AGENT_WATCH_COST_USD: 0.005,
                otel.GEN_AI_USAGE_INPUT_TOKENS: 500,
                otel.GEN_AI_USAGE_OUTPUT_TOKENS: 200,
            },
        ),
        Span(
            span_id="evt-2",
            trace_id="evt-1",
            kind=otel.KIND_LLM,
            name="call_claude",
            parent_span_id="evt-1",
            start_time=now - 99.5,
            end_time=now - 98.5,
            duration_ms=1000.0,
            status=otel.STATUS_OK,
            attributes={
                otel.GEN_AI_REQUEST_MODEL: "claude-sonnet-4-20250514",
                otel.GEN_AI_USAGE_INPUT_TOKENS: 500,
                otel.GEN_AI_USAGE_OUTPUT_TOKENS: 200,
                otel.AGENT_WATCH_COST_USD: 0.0045,
            },
        ),
        Span(
            span_id="evt-3",
            trace_id="evt-3",
            kind=otel.KIND_AGENT,
            name="code-reviewer",
            start_time=now - 90,
            end_time=now - 85,
            duration_ms=5000.0,
            status=otel.STATUS_ERROR,
            error="Context length exceeded",
            attributes={
                otel.AGENT_WATCH_COST_USD: 0.01,
                otel.GEN_AI_USAGE_INPUT_TOKENS: 8000,
                otel.GEN_AI_USAGE_OUTPUT_TOKENS: 0,
            },
        ),
        Span(
            span_id="evt-4",
            trace_id="evt-4",
            kind=otel.KIND_AGENT,
            name="research-agent",
            start_time=now - 80,
            end_time=now - 78,
            duration_ms=2000.0,
            status=otel.STATUS_OK,
            attributes={
                otel.AGENT_WATCH_COST_USD: 0.006,
                otel.GEN_AI_USAGE_INPUT_TOKENS: 600,
                otel.GEN_AI_USAGE_OUTPUT_TOKENS: 250,
            },
        ),
    ]

    with open(filepath, "w") as f:
        for span in spans:
            f.write(span.to_json() + "\n")

    return spans
```

Also update the fixture's import line at top of conftest: replace `from agent_watch.types import Event` with `from agent_watch.types import Span`.

- [ ] **Step 2: Update `src/agent_watch/storage.py`**

Replace the entire contents with:

```python
"""Read and query telemetry data from JSONL files."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from agent_watch import otel
from agent_watch.collector import get_storage_dir
from agent_watch.types import Span


def load_spans(
    days: int = 7,
    agent_name: Optional[str] = None,
    status: Optional[str] = None,
    kind: Optional[str] = None,
    storage_dir: Optional[Path] = None,
) -> List[Span]:
    """Load spans from JSONL files, with optional filtering."""
    dir_path = storage_dir or get_storage_dir()
    if not dir_path.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    spans: List[Span] = []

    for filepath in sorted(dir_path.glob("*.jsonl")):
        try:
            file_date = datetime.strptime(filepath.stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if file_date < cutoff - timedelta(days=1):
                continue
        except ValueError:
            continue

        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    span = Span.from_json(line)
                except (json.JSONDecodeError, TypeError):
                    continue

                if agent_name and span.name != agent_name:
                    continue
                if status and span.status != status:
                    continue
                if kind and span.kind != kind:
                    continue
                if span.start_time < cutoff.timestamp():
                    continue

                spans.append(span)

    return spans


# Back-compat alias for code that still calls load_events
def load_events(
    days: int = 7,
    agent_name: Optional[str] = None,
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    storage_dir: Optional[Path] = None,
) -> List[Span]:
    kind_map = {"agent_run": otel.KIND_AGENT, "llm_call": otel.KIND_LLM, "span": otel.KIND_SPAN}
    kind = kind_map.get(event_type) if event_type else None
    status_map = {"success": otel.STATUS_OK, "error": otel.STATUS_ERROR}
    mapped_status = status_map.get(status, status) if status else None
    return load_spans(
        days=days, agent_name=agent_name, status=mapped_status, kind=kind, storage_dir=storage_dir
    )


def aggregate_by_agent(spans: List[Span]) -> Dict[str, AgentStats]:
    stats: Dict[str, AgentStats] = {}
    for span in spans:
        if span.kind != otel.KIND_AGENT:
            continue
        if span.name not in stats:
            stats[span.name] = AgentStats(name=span.name)
        stats[span.name].add(span)
    return stats


def aggregate_by_model(spans: List[Span]) -> Dict[str, ModelStats]:
    stats: Dict[str, ModelStats] = {}
    for span in spans:
        if span.kind != otel.KIND_LLM:
            continue
        model = span.attributes.get(otel.GEN_AI_REQUEST_MODEL, "unknown")
        if model not in stats:
            stats[model] = ModelStats(model=model)
        stats[model].add(span)
    return stats


class AgentStats:
    def __init__(self, name: str):
        self.name = name
        self.total_runs = 0
        self.successes = 0
        self.failures = 0
        self.total_duration_ms = 0.0
        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.error_messages: list[str] = []

    def add(self, span: Span) -> None:
        self.total_runs += 1
        if span.status == otel.STATUS_OK:
            self.successes += 1
        else:
            self.failures += 1
            if span.error:
                self.error_messages.append(span.error)
        self.total_duration_ms += span.duration_ms
        self.total_cost += span.attributes.get(otel.AGENT_WATCH_COST_USD, 0.0)
        self.total_input_tokens += span.attributes.get(otel.GEN_AI_USAGE_INPUT_TOKENS, 0)
        self.total_output_tokens += span.attributes.get(otel.GEN_AI_USAGE_OUTPUT_TOKENS, 0)

    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.successes / self.total_runs

    @property
    def avg_duration_ms(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.total_duration_ms / self.total_runs


class ModelStats:
    def __init__(self, model: str):
        self.model = model
        self.total_calls = 0
        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_duration_ms = 0.0

    def add(self, span: Span) -> None:
        self.total_calls += 1
        self.total_cost += span.attributes.get(otel.AGENT_WATCH_COST_USD, 0.0)
        self.total_input_tokens += span.attributes.get(otel.GEN_AI_USAGE_INPUT_TOKENS, 0)
        self.total_output_tokens += span.attributes.get(otel.GEN_AI_USAGE_OUTPUT_TOKENS, 0)
        self.total_duration_ms += span.duration_ms

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def avg_duration_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_duration_ms / self.total_calls
```

- [ ] **Step 3: Update `tests/test_storage.py`**

Run: `cat tests/test_storage.py` and apply the same field-name replacements: `type`→`kind`, `metadata`→`attributes`, `event_type`→`kind` where the test calls `load_events(event_type=...)`. Where tests assert on `stats.total_cost`, `stats.total_input_tokens`, etc., those API names did not change.

- [ ] **Step 4: Run storage tests**

Run: `pytest tests/test_storage.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_watch/storage.py tests/test_storage.py tests/conftest.py
git commit -m "feat(storage): read Span schema, back-compat load_events alias"
```

---

### Task 8: Update all CLI commands to read new attribute keys

**Files:**
- Modify: `src/agent_watch/cli/status.py`, `costs.py`, `traces.py`, `report.py`, `alerts.py`, `formatting.py`
- Test: `tests/test_cli_status.py`, `test_cli_costs.py`, `test_cli_report.py`, `test_cli_alerts.py`

- [ ] **Step 1: Scan CLI files for old field references**

Run: `grep -n 'metadata\[' src/agent_watch/cli/*.py`
Run: `grep -n 'event\.' src/agent_watch/cli/*.py`
Run: `grep -n '\.type' src/agent_watch/cli/*.py`
Run: `grep -n '"success"' src/agent_watch/cli/*.py`
Run: `grep -n '"agent_run"\|"llm_call"' src/agent_watch/cli/*.py`

Record every line number reported.

- [ ] **Step 2: Apply attribute-key migrations**

In each CLI file, for every old reference found in Step 1, apply:
- `event.metadata["model"]` → `span.attributes.get(otel.GEN_AI_REQUEST_MODEL, "")`
- `event.metadata["cost_usd"]` → `span.attributes.get(otel.AGENT_WATCH_COST_USD, 0.0)`
- `event.metadata["input_tokens"]` → `span.attributes.get(otel.GEN_AI_USAGE_INPUT_TOKENS, 0)`
- `event.metadata["output_tokens"]` → `span.attributes.get(otel.GEN_AI_USAGE_OUTPUT_TOKENS, 0)`
- `event.metadata["tags"]` → `span.attributes.get(otel.AGENT_WATCH_TAGS, [])`
- `event.type == "agent_run"` → `span.kind == otel.KIND_AGENT`
- `event.type == "llm_call"` → `span.kind == otel.KIND_LLM`
- `event.status == "success"` → `span.status == otel.STATUS_OK`

Add `from agent_watch import otel` at the top of each modified CLI file.

Rename local variables from `event` / `events` to `span` / `spans` only where it improves clarity; leave loop variables named `event` if changing them would cascade. The data access is what matters.

- [ ] **Step 3: Run all CLI tests**

Run: `pytest tests/test_cli_*.py -v`
Expected: all PASS

- [ ] **Step 4: Manual smoke test**

Run:
```bash
rm -rf .agent-watch
python -c "
from agent_watch import trace_agent, trace_llm_call
import asyncio

@trace_llm_call(model='gpt-4o')
async def call(p):
    return {'content': 'ok', 'input_tokens': 100, 'output_tokens': 50}

@trace_agent(name='smoke')
async def run():
    return await call('hi')

asyncio.run(run())
"
agent-watch status
agent-watch costs
```

Expected: `status` shows 1 agent run, `costs` shows gpt-4o cost.

- [ ] **Step 5: Commit**

```bash
git add src/agent_watch/cli/
git commit -m "feat(cli): read v1 Span attribute keys"
```

---

### Task 9: Update `__init__.py` public API

**Files:**
- Modify: `src/agent_watch/__init__.py`

- [ ] **Step 1: Rewrite `src/agent_watch/__init__.py`**

Replace with:

```python
"""Agent Watch: observability and cost enforcement for AI agents."""

__version__ = "1.0.0.dev0"

from agent_watch.decorators import trace_agent, trace_llm_call
from agent_watch.span import Span as SpanContext
from agent_watch.types import Span as SpanRecord
from agent_watch.types import Span  # public: the telemetry dataclass

# v0.1 names kept as deprecation aliases
Event = SpanRecord
from agent_watch.span import Span as _SpanContextManager  # noqa: F401

__all__ = [
    "trace_agent",
    "trace_llm_call",
    "Span",  # telemetry dataclass
    "SpanContext",  # context manager (renamed for clarity)
    "Event",  # deprecated
]
```

Note: The `Span` name is overloaded (both a dataclass and a context manager). The public `Span` export is now the context manager to keep backward compatibility with v0.1 user code (`with Span("x") as s:`). The dataclass is available as `SpanRecord` for advanced users.

Correction: Re-export so that public API matches v0.1 behavior. Use this version instead:

```python
"""Agent Watch: observability and cost enforcement for AI agents."""

__version__ = "1.0.0.dev0"

from agent_watch.decorators import trace_agent, trace_llm_call
from agent_watch.span import Span  # context manager
from agent_watch.types import Span as SpanRecord  # dataclass (for exporters, advanced use)

# v0.1 deprecated alias
Event = SpanRecord

__all__ = ["trace_agent", "trace_llm_call", "Span", "SpanRecord", "Event"]
```

- [ ] **Step 2: Run full suite**

Run: `pytest -v`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/agent_watch/__init__.py
git commit -m "feat: export Span context manager and SpanRecord dataclass"
```

---

### Task 10: Backward-compat read test for v0.1 JSONL

**Files:**
- Test: `tests/test_otel_schema.py` (append)

- [ ] **Step 1: Add integration test that storage reads v0.1 files**

Append to `tests/test_otel_schema.py`:

```python
def test_storage_reads_v01_legacy_file(temp_storage):
    """Files written by v0.1 remain readable after v1.0 upgrade."""
    from datetime import datetime, timezone
    from agent_watch.storage import load_spans

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filepath = temp_storage / f"{today}.jsonl"

    import time
    now = time.time()
    legacy_line = (
        '{"id": "legacy-1", "type": "agent_run", "name": "v01-agent", '
        f'"parent_id": null, "start_time": {now - 10}, "end_time": {now - 9}, '
        '"duration_ms": 1000.0, "status": "success", "error": null, '
        '"input_preview": null, "output_preview": null, '
        '"metadata": {"model": "gpt-4", "cost_usd": 0.42, "input_tokens": 100, "output_tokens": 50}, '
        '"children": []}\n'
    )
    filepath.write_text(legacy_line)

    spans = load_spans(days=1, storage_dir=temp_storage)
    assert len(spans) == 1
    assert spans[0].name == "v01-agent"
    assert spans[0].kind == otel.KIND_AGENT
    assert spans[0].status == otel.STATUS_OK
    assert spans[0].attributes[otel.AGENT_WATCH_COST_USD] == 0.42
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_otel_schema.py::test_storage_reads_v01_legacy_file -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_otel_schema.py
git commit -m "test: verify v0.1 JSONL files remain readable by v1.0"
```

---

### Task 11: Bump version and update pyproject

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update version**

In `pyproject.toml`, change `version = "0.1.0"` to `version = "1.0.0.dev0"` and update the description to reflect the new positioning:

```toml
description = "Circuit breaker for runaway agent bills. Hard budget enforcement, OTel-native, zero-config Python CLI."
```

Keep everything else unchanged.

- [ ] **Step 2: Run tests**

Run: `pytest -v`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump to 1.0.0.dev0, update description for v1 positioning"
```

---

## Phase 2: Hard Budget Enforcement

### Task 12: Create Budget module and BudgetExceeded exception

**Files:**
- Create: `src/agent_watch/budget.py`
- Create: `tests/test_budget.py`

- [ ] **Step 1: Write failing tests for Budget primitives**

Create `tests/test_budget.py`:

```python
"""Tests for budget enforcement."""

import pytest
from agent_watch.budget import Budget, BudgetExceeded


def test_budget_exceeded_has_diagnostic_fields():
    err = BudgetExceeded(spent_usd=5.50, budget_usd=5.00, agent_name="loop")
    assert err.spent_usd == 5.50
    assert err.budget_usd == 5.00
    assert err.agent_name == "loop"
    assert "5.50" in str(err)
    assert "5.00" in str(err)
    assert "loop" in str(err)


def test_budget_tracks_spend():
    b = Budget(cap_usd=10.0, agent_name="x")
    assert b.spent_usd == 0.0
    b.add_spend(1.50)
    b.add_spend(0.75)
    assert b.spent_usd == pytest.approx(2.25)


def test_budget_under_cap_does_not_raise():
    b = Budget(cap_usd=5.0, agent_name="x")
    b.add_spend(1.0)
    b.check()  # should not raise


def test_budget_over_cap_raises():
    b = Budget(cap_usd=5.0, agent_name="y")
    b.add_spend(3.0)
    b.add_spend(2.5)
    with pytest.raises(BudgetExceeded) as exc_info:
        b.check()
    assert exc_info.value.spent_usd == pytest.approx(5.5)
    assert exc_info.value.budget_usd == 5.0
    assert exc_info.value.agent_name == "y"


def test_budget_warn_mode_does_not_raise():
    b = Budget(cap_usd=5.0, agent_name="z", on_exceed="warn")
    b.add_spend(10.0)
    b.check()  # must not raise


def test_budget_exceeded_flag():
    b = Budget(cap_usd=5.0, agent_name="x")
    assert not b.is_exceeded()
    b.add_spend(10.0)
    assert b.is_exceeded()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_budget.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/agent_watch/budget.py`**

Create the file with:

```python
"""Budget enforcement primitives.

A Budget is a running USD cap scoped to a tracing context. Decorators push a
Budget onto the stack when a trace_agent has a budget_usd kwarg or when
AGENT_WATCH_BUDGET_USD is set. Each traced LLM call calls Budget.add_spend(cost)
and Budget.check() after cost is computed. If check() finds the active budget
over its cap, it raises BudgetExceeded, which propagates out of the LLM call
and stops any subsequent calls in the loop.
"""

from __future__ import annotations

import contextvars
import os
from typing import List, Literal, Optional


class BudgetExceeded(RuntimeError):
    """Raised when a tracing context exceeds its USD budget cap."""

    def __init__(self, spent_usd: float, budget_usd: float, agent_name: str):
        self.spent_usd = spent_usd
        self.budget_usd = budget_usd
        self.agent_name = agent_name
        super().__init__(
            f"Budget exceeded for '{agent_name}': spent ${spent_usd:.2f} of ${budget_usd:.2f}"
        )


class Budget:
    """A USD cap plus running spend for a tracing context."""

    def __init__(
        self,
        cap_usd: float,
        agent_name: str = "",
        on_exceed: Literal["raise", "warn"] = "raise",
    ):
        self.cap_usd = cap_usd
        self.agent_name = agent_name
        self.on_exceed = on_exceed
        self.spent_usd = 0.0
        self._exceeded = False

    def add_spend(self, cost_usd: float) -> None:
        if cost_usd and cost_usd > 0:
            self.spent_usd += cost_usd
            if self.spent_usd > self.cap_usd:
                self._exceeded = True

    def is_exceeded(self) -> bool:
        return self._exceeded

    def check(self) -> None:
        if self._exceeded and self.on_exceed == "raise":
            raise BudgetExceeded(
                spent_usd=self.spent_usd,
                budget_usd=self.cap_usd,
                agent_name=self.agent_name,
            )


# Stack of active budgets. Nested agents push/pop.
_budget_stack_var: contextvars.ContextVar[List[Budget]] = contextvars.ContextVar(
    "agent_watch_budget_stack", default=[]
)


def push_budget(budget: Budget) -> List[Budget]:
    current = list(_budget_stack_var.get())
    previous = current
    current.append(budget)
    _budget_stack_var.set(current)
    return previous


def pop_budget(previous: List[Budget]) -> None:
    _budget_stack_var.set(previous)


def active_budgets() -> List[Budget]:
    return list(_budget_stack_var.get())


def record_spend(cost_usd: float) -> None:
    """Add spend to every budget currently on the stack (parent budgets see child spend)."""
    for b in _budget_stack_var.get():
        b.add_spend(cost_usd)


def check_all_budgets() -> None:
    """Raise BudgetExceeded if any active budget is over its cap in 'raise' mode.

    Checks outermost first so that when a nested call exceeds a parent budget,
    the parent's error is what the user sees.
    """
    for b in _budget_stack_var.get():
        b.check()


def get_env_budget_cap_usd() -> Optional[float]:
    """Read AGENT_WATCH_BUDGET_USD env var as a float cap, or return None."""
    value = os.environ.get("AGENT_WATCH_BUDGET_USD")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_budget.py -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_watch/budget.py tests/test_budget.py
git commit -m "feat(budget): add Budget class, BudgetExceeded, context stack"
```

---

### Task 13: Wire budget_usd kwarg into trace_agent decorator

**Files:**
- Modify: `src/agent_watch/decorators.py`
- Test: `tests/test_budget.py` (append)

- [ ] **Step 1: Write failing test for decorator budget enforcement**

Append to `tests/test_budget.py`:

```python
import asyncio
from agent_watch import trace_agent, trace_llm_call
from agent_watch.budget import BudgetExceeded


def test_trace_agent_with_budget_under_cap_does_not_raise(temp_storage):
    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        return {"content": "ok", "input_tokens": 100, "output_tokens": 50}

    @trace_agent(name="cheap", budget_usd=10.0)
    def run():
        return call("hi")

    result = run()
    assert result["content"] == "ok"


def test_trace_agent_raises_budget_exceeded_after_over_cap_call(temp_storage):
    """Single over-cap call: the call fires, but the decorator raises on exit."""
    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        # This one call costs 100 * 2.50/1M + 50 * 10/1M = $0.00075
        return {"content": "x", "input_tokens": 100, "output_tokens": 50}

    @trace_agent(name="tight", budget_usd=0.0001)  # cap below single-call cost
    def run():
        return call("hi")

    with pytest.raises(BudgetExceeded) as exc_info:
        run()
    assert exc_info.value.agent_name == "tight"
    assert exc_info.value.budget_usd == 0.0001
    assert exc_info.value.spent_usd > 0.0001


def test_trace_agent_budget_stops_second_call_in_loop(temp_storage):
    """After first over-cap call, next call is not made because exception propagated."""
    call_count = {"n": 0}

    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        call_count["n"] += 1
        return {"content": "x", "input_tokens": 1000, "output_tokens": 500}

    @trace_agent(name="loop", budget_usd=0.0001)
    def run():
        for i in range(10):
            call(f"turn {i}")
        return "done"

    with pytest.raises(BudgetExceeded):
        run()
    assert call_count["n"] == 1  # second call never fires


def test_trace_agent_budget_warn_mode_does_not_raise(temp_storage):
    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        return {"content": "x", "input_tokens": 1000, "output_tokens": 500}

    @trace_agent(name="warner", budget_usd=0.0001, on_exceed="warn")
    def run():
        for i in range(3):
            call(f"turn {i}")
        return "done"

    result = run()  # must not raise
    assert result == "done"


@pytest.mark.asyncio
async def test_trace_agent_budget_async(temp_storage):
    @trace_llm_call(model="gpt-4o")
    async def call(p: str) -> dict:
        return {"content": "x", "input_tokens": 10000, "output_tokens": 5000}

    @trace_agent(name="a", budget_usd=0.0001)
    async def run():
        await call("x")
        await call("y")
        return "done"

    with pytest.raises(BudgetExceeded):
        await run()


def test_env_budget_cap(temp_storage, monkeypatch):
    monkeypatch.setenv("AGENT_WATCH_BUDGET_USD", "0.0001")

    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        return {"content": "x", "input_tokens": 1000, "output_tokens": 500}

    @trace_agent(name="env")
    def run():
        for i in range(5):
            call(f"turn {i}")

    with pytest.raises(BudgetExceeded):
        run()
```

- [ ] **Step 2: Run tests to see failures**

Run: `pytest tests/test_budget.py -v`
Expected: new tests FAIL

- [ ] **Step 3: Update `src/agent_watch/decorators.py` to accept budget_usd and on_exceed**

At the top of the file, add:

```python
from agent_watch.budget import (
    Budget,
    BudgetExceeded,
    active_budgets,
    check_all_budgets,
    get_env_budget_cap_usd,
    pop_budget,
    push_budget,
    record_spend,
)
```

Replace the `trace_agent` function signature and body with:

```python
def trace_agent(
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    budget_usd: Optional[float] = None,
    on_exceed: str = "raise",
) -> Callable:
    """Trace an agent function (sync or async).

    Args:
        name: Agent name (defaults to function name).
        tags: Optional list of tags.
        budget_usd: Optional USD cap. If total cost in this agent (and children)
            exceeds this, BudgetExceeded is raised after the offending LLM call.
            Overrides AGENT_WATCH_BUDGET_USD env var.
        on_exceed: "raise" (default) or "warn". Only applies when budget_usd is set
            or env var is set.
    """

    def decorator(func: Callable) -> Callable:
        agent_name = name or func.__name__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                return await _run_agent_async(func, agent_name, tags, budget_usd, on_exceed, args, kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return _run_agent_sync(func, agent_name, tags, budget_usd, on_exceed, args, kwargs)

        return sync_wrapper

    return decorator
```

Update `_run_agent_async` and `_run_agent_sync` to manage the budget stack:

```python
def _resolve_budget(agent_name: str, budget_usd: Optional[float], on_exceed: str) -> Optional[Budget]:
    cap = budget_usd if budget_usd is not None else get_env_budget_cap_usd()
    if cap is None:
        return None
    return Budget(cap_usd=cap, agent_name=agent_name, on_exceed=on_exceed)


async def _run_agent_async(func, agent_name, tags, budget_usd, on_exceed, args, kwargs):
    budget = _resolve_budget(agent_name, budget_usd, on_exceed)
    previous_stack = push_budget(budget) if budget else None
    span, prev_parent, prev_trace = _start_agent_span(agent_name, tags)
    span.input_preview = preview(_format_args(args, kwargs))
    if budget:
        span.attributes[otel.AGENT_WATCH_BUDGET_USD] = budget.cap_usd
    try:
        result = await func(*args, **kwargs)
        span.output_preview = preview(result)
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_OK, None)
        return result
    except BudgetExceeded as e:
        span.attributes[otel.AGENT_WATCH_BUDGET_EXCEEDED] = True
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise
    except Exception as e:
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise
    finally:
        if previous_stack is not None:
            pop_budget(previous_stack)


def _run_agent_sync(func, agent_name, tags, budget_usd, on_exceed, args, kwargs):
    budget = _resolve_budget(agent_name, budget_usd, on_exceed)
    previous_stack = push_budget(budget) if budget else None
    span, prev_parent, prev_trace = _start_agent_span(agent_name, tags)
    span.input_preview = preview(_format_args(args, kwargs))
    if budget:
        span.attributes[otel.AGENT_WATCH_BUDGET_USD] = budget.cap_usd
    try:
        result = func(*args, **kwargs)
        span.output_preview = preview(result)
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_OK, None)
        return result
    except BudgetExceeded as e:
        span.attributes[otel.AGENT_WATCH_BUDGET_EXCEEDED] = True
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise
    except Exception as e:
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise
    finally:
        if previous_stack is not None:
            pop_budget(previous_stack)
```

Note: The old `_run_agent_async` and `_run_agent_sync` signatures changed (budget args added). The old call sites inside `trace_agent` are also updated above. Delete the old versions.

- [ ] **Step 4: Wire spend recording + budget check into LLM helpers**

In `src/agent_watch/decorators.py`, update `_extract_llm_attributes` to record spend, and update `_run_llm_async` / `_run_llm_sync` to check budgets after extraction:

```python
def _extract_llm_attributes(span: Span, result: Any, model: str) -> None:
    input_tokens = 0
    output_tokens = 0
    content = ""

    if isinstance(result, dict):
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        content = result.get("content", "")
    elif hasattr(result, "input_tokens"):
        input_tokens = getattr(result, "input_tokens", 0)
        output_tokens = getattr(result, "output_tokens", 0)
        content = getattr(result, "content", "")
    elif isinstance(result, str):
        content = result

    span.attributes[otel.GEN_AI_USAGE_INPUT_TOKENS] = input_tokens
    span.attributes[otel.GEN_AI_USAGE_OUTPUT_TOKENS] = output_tokens
    span.output_preview = preview(content)

    if model and (input_tokens or output_tokens):
        cost = estimate_cost(model, input_tokens, output_tokens)
        if cost is not None:
            span.attributes[otel.AGENT_WATCH_COST_USD] = cost
            record_spend(cost)
```

Update the LLM runners to call `check_all_budgets()` after extraction:

```python
async def _run_llm_async(func: Callable, call_name: str, model: str, args, kwargs) -> Any:
    span, prev_parent, prev_trace = _start_llm_span(call_name, model)
    span.input_preview = preview(_format_args(args, kwargs))
    try:
        result = await func(*args, **kwargs)
        _extract_llm_attributes(span, result, model)
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_OK, None)
        check_all_budgets()
        return result
    except BudgetExceeded:
        raise
    except Exception as e:
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise


def _run_llm_sync(func: Callable, call_name: str, model: str, args, kwargs) -> Any:
    span, prev_parent, prev_trace = _start_llm_span(call_name, model)
    span.input_preview = preview(_format_args(args, kwargs))
    try:
        result = func(*args, **kwargs)
        _extract_llm_attributes(span, result, model)
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_OK, None)
        check_all_budgets()
        return result
    except BudgetExceeded:
        raise
    except Exception as e:
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise
```

Important: `check_all_budgets()` is called *after* `_finish_span` so the LLM span is fully written to disk before the exception fires. Users get a complete trace record of the call that tipped them over.

- [ ] **Step 5: Run budget tests**

Run: `pytest tests/test_budget.py -v`
Expected: all tests PASS

- [ ] **Step 6: Run full suite to check nothing regressed**

Run: `pytest -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/agent_watch/decorators.py tests/test_budget.py
git commit -m "feat(budget): enforce budget_usd on trace_agent, env var fallback"
```

---

### Task 14: Nested budget inheritance test

**Files:**
- Test: `tests/test_budget.py` (append)

- [ ] **Step 1: Write test**

Append:

```python
def test_nested_agents_both_budgets_count_spend(temp_storage):
    """Parent and child budgets both accumulate spend from LLM calls anywhere underneath."""
    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        return {"content": "x", "input_tokens": 500, "output_tokens": 250}

    @trace_agent(name="child", budget_usd=10.0)
    def child():
        call("inner")
        return "child-done"

    @trace_agent(name="parent", budget_usd=0.0001)  # parent cap tight
    def parent():
        child()
        return "parent-done"

    with pytest.raises(BudgetExceeded) as exc_info:
        parent()
    # Parent budget should be the one that trips
    assert exc_info.value.agent_name == "parent"


def test_sibling_agents_do_not_share_budget(temp_storage):
    """Two sequential agents with their own budgets: spend in one does not affect the other."""
    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        return {"content": "x", "input_tokens": 100, "output_tokens": 50}

    @trace_agent(name="a", budget_usd=10.0)
    def a():
        call("a")
        return "ok"

    @trace_agent(name="b", budget_usd=10.0)
    def b():
        call("b")
        return "ok"

    assert a() == "ok"
    assert b() == "ok"
```

- [ ] **Step 2: Run**

Run: `pytest tests/test_budget.py -v`
Expected: all PASS (the Budget stack design makes this work already)

- [ ] **Step 3: Commit**

```bash
git add tests/test_budget.py
git commit -m "test(budget): verify nested inheritance and sibling isolation"
```

---

### Task 15: Export BudgetExceeded from public API

**Files:**
- Modify: `src/agent_watch/__init__.py`

- [ ] **Step 1: Update exports**

Replace the `__init__.py` contents with:

```python
"""Agent Watch: observability and cost enforcement for AI agents."""

__version__ = "1.0.0.dev0"

from agent_watch.budget import BudgetExceeded
from agent_watch.decorators import trace_agent, trace_llm_call
from agent_watch.span import Span  # context manager
from agent_watch.types import Span as SpanRecord  # dataclass

# v0.1 deprecated alias
Event = SpanRecord

__all__ = [
    "trace_agent",
    "trace_llm_call",
    "Span",
    "SpanRecord",
    "Event",
    "BudgetExceeded",
]
```

- [ ] **Step 2: Smoke test the import**

Run:
```bash
python -c "from agent_watch import trace_agent, trace_llm_call, BudgetExceeded, Span; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/agent_watch/__init__.py
git commit -m "feat: export BudgetExceeded at package root"
```

---

### Task 16: Update README.md with budget snippet

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite tagline and first code example**

In `README.md`, replace the tagline line:
`**Know what your agents cost before you get the bill.**`
with:
`**The circuit breaker your agents don't have. Set a budget. Get a kill-switch.**`

Immediately after the first `pip install agent-watch` block, add a new code block showing the enforcement feature:

````markdown
```python
from agent_watch import trace_agent, trace_llm_call, BudgetExceeded

@trace_agent(name="research", budget_usd=5.00)
async def research(topic: str) -> str:
    # Your agent loop. If cumulative spend crosses $5.00,
    # the next LLM call raises BudgetExceeded instead of firing.
    return await run_loop(topic)

try:
    await research("competitor pricing")
except BudgetExceeded as e:
    log.error(f"Killed at ${e.spent_usd:.2f} of ${e.budget_usd:.2f}")
```
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): lead with circuit-breaker positioning and budget snippet"
```

---

### Task 17: Final self-check

- [ ] **Step 1: Full test suite with coverage sanity**

Run: `pytest -v`
Expected: 100% tests PASS

- [ ] **Step 2: Ruff lint check**

Run: `ruff check src/ tests/`
Expected: no errors

- [ ] **Step 3: Manual smoke test end to end**

Run:
```bash
rm -rf .agent-watch
python <<'PY'
from agent_watch import trace_agent, trace_llm_call, BudgetExceeded

call_count = 0

@trace_llm_call(model="gpt-4o")
def call(p: str) -> dict:
    global call_count
    call_count += 1
    return {"content": "x", "input_tokens": 1000, "output_tokens": 500}

@trace_agent(name="runaway", budget_usd=0.01)
def run():
    for i in range(100):
        call(f"turn {i}")

try:
    run()
except BudgetExceeded as e:
    print(f"Circuit-breaker tripped at ${e.spent_usd:.4f} of ${e.budget_usd:.4f}")
    print(f"Killed after {call_count} LLM calls (out of 100 planned)")
PY
```

Expected output: message printed, `call_count` much less than 100.

Then:
```bash
agent-watch status
agent-watch traces --status error
```

Expected: `status` shows the agent run with `error` status, `traces --status error` shows the failed run.

- [ ] **Step 4: Commit any cleanup if needed, otherwise mark phase complete**

```bash
git log --oneline v1.0-foundation ^main
```

Expected: sequence of feat/test/docs commits for Phase 1 and Phase 2.

---

## Risks and Open Questions

1. **Async budget accounting race**: If two `asyncio.gather` tasks each make LLM calls in parallel, both may add spend before either calls `check_all_budgets`. This is acceptable for v1.0 (the next serial call will still trip), but worth documenting.

2. **`on_exceed="warn"` mode has no warning output yet**: The current implementation just skips raising. Before Show HN, add a one-line stderr message in warn mode: `[agent-watch] WARNING: budget exceeded ...`. Not blocking for merge but needed before launch.

3. **Cost rounding**: `estimate_cost` rounds to 6 decimal places. For very low-cost calls (Haiku, mini models), single-call cost can be below the rounding threshold. Verify that `if cost_usd and cost_usd > 0` in `Budget.add_spend` still accumulates these correctly over many calls. If it becomes an issue, drop the `> 0` check.

4. **Deprecation warnings**: The `Event` alias is exported but has no `DeprecationWarning`. Consider adding one before v1.0 final.

5. **CLI `budgets` command**: The ROADMAP mentions `agent-watch budgets` showing active caps. This is not in Plan 1 (active budgets live in-process, so a CLI command would only show what's in emitted spans). Plan 3 (developer tools) is a better home.

---

## Execution Notes

- Each task is a self-contained commit. If a step block grows beyond what fits in a single focused session, split at the commit boundary.
- The OTel schema migration (Tasks 2-11) is the highest-risk phase because it touches every module. Budget changes (Tasks 12-16) ride on top cleanly.
- Do not run the full test suite between every task — pytest the just-modified module first, then run the full suite at task boundaries. The CI pipeline catches regressions on push.
- After Phase 1 (schema) is merged, Phase 2 (budget) can be resumed in a fresh session with just this plan as context.

"""Shared test fixtures."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import pytest

from agent_watch.types import Span


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    """Use a temporary directory for all test storage."""
    storage_dir = tmp_path / ".agent-watch"
    storage_dir.mkdir()
    monkeypatch.setenv("AGENT_WATCH_DIR", str(storage_dir))
    # Reset context variables between tests
    import agent_watch.collector as collector
    collector._parent_id_var.set(None)
    collector._children_var.set({})
    collector._trace_id_var.set(None)
    return storage_dir


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

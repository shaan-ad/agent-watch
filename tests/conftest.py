"""Shared test fixtures."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import pytest

from agent_watch.types import Event


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
    return storage_dir


@pytest.fixture
def sample_events(temp_storage) -> List[Event]:
    """Write sample events to storage and return them."""
    import time
    now = time.time()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filepath = temp_storage / f"{today}.jsonl"

    events = [
        Event(
            id="evt-1",
            type="agent_run",
            name="research-agent",
            start_time=now - 100,
            end_time=now - 98,
            duration_ms=2000.0,
            status="success",
            input_preview="quantum computing",
            output_preview="Summary of quantum computing...",
            metadata={"tags": ["test"], "cost_usd": 0.005, "input_tokens": 500, "output_tokens": 200},
        ),
        Event(
            id="evt-2",
            type="llm_call",
            name="call_claude",
            parent_id="evt-1",
            start_time=now - 99.5,
            end_time=now - 98.5,
            duration_ms=1000.0,
            status="success",
            metadata={"model": "claude-sonnet-4-20250514", "input_tokens": 500, "output_tokens": 200, "cost_usd": 0.0045},
        ),
        Event(
            id="evt-3",
            type="agent_run",
            name="code-reviewer",
            start_time=now - 90,
            end_time=now - 85,
            duration_ms=5000.0,
            status="error",
            error="Context length exceeded",
            metadata={"cost_usd": 0.01, "input_tokens": 8000, "output_tokens": 0},
        ),
        Event(
            id="evt-4",
            type="agent_run",
            name="research-agent",
            start_time=now - 80,
            end_time=now - 78,
            duration_ms=2000.0,
            status="success",
            metadata={"cost_usd": 0.006, "input_tokens": 600, "output_tokens": 250},
        ),
    ]

    with open(filepath, "w") as f:
        for event in events:
            f.write(event.to_json() + "\n")

    return events

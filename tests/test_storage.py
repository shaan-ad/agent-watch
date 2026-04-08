"""Tests for storage reading and querying."""

from __future__ import annotations


from agent_watch.storage import (
    AgentStats,
    aggregate_by_agent,
    aggregate_by_model,
    load_events,
)


def test_load_events_from_sample(sample_events, temp_storage):
    events = load_events(days=30, storage_dir=temp_storage)
    assert len(events) == 4


def test_load_events_filter_by_name(sample_events, temp_storage):
    events = load_events(days=30, agent_name="research-agent", storage_dir=temp_storage)
    assert all(e.name == "research-agent" for e in events)
    assert len(events) == 2


def test_load_events_filter_by_status(sample_events, temp_storage):
    events = load_events(days=30, status="error", storage_dir=temp_storage)
    assert all(e.status == "error" for e in events)
    assert len(events) == 1


def test_load_events_filter_by_type(sample_events, temp_storage):
    events = load_events(days=30, event_type="llm_call", storage_dir=temp_storage)
    assert all(e.type == "llm_call" for e in events)
    assert len(events) == 1


def test_load_events_empty_dir(temp_storage):
    events = load_events(days=7, storage_dir=temp_storage)
    assert events == []


def test_aggregate_by_agent(sample_events, temp_storage):
    events = load_events(days=30, storage_dir=temp_storage)
    stats = aggregate_by_agent(events)

    assert "research-agent" in stats
    assert "code-reviewer" in stats

    research = stats["research-agent"]
    assert research.total_runs == 2
    assert research.successes == 2
    assert research.failures == 0
    assert research.success_rate == 1.0

    reviewer = stats["code-reviewer"]
    assert reviewer.total_runs == 1
    assert reviewer.failures == 1
    assert reviewer.success_rate == 0.0


def test_aggregate_by_model(sample_events, temp_storage):
    events = load_events(days=30, storage_dir=temp_storage)
    stats = aggregate_by_model(events)

    assert "claude-sonnet-4-20250514" in stats
    model = stats["claude-sonnet-4-20250514"]
    assert model.total_calls == 1
    assert model.total_input_tokens == 500
    assert model.total_output_tokens == 200


def test_agent_stats_avg_duration():
    stats = AgentStats(name="test")
    from agent_watch.types import Event

    e1 = Event(type="agent_run", name="test", duration_ms=1000)
    e2 = Event(type="agent_run", name="test", duration_ms=3000)
    stats.add(e1)
    stats.add(e2)

    assert stats.avg_duration_ms == 2000.0

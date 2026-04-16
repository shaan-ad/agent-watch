"""Tests for decorators."""

from __future__ import annotations

import json

import pytest

from agent_watch import otel
from agent_watch.decorators import trace_agent, trace_llm_call


def _read_events(storage_dir):
    events = []
    for f in storage_dir.glob("*.jsonl"):
        for line in open(f):
            events.append(json.loads(line))
    return events


@pytest.mark.asyncio
async def test_trace_agent_async(temp_storage):
    @trace_agent(name="test-agent")
    async def my_agent(query: str) -> str:
        return f"Result for {query}"

    result = await my_agent("hello")
    assert result == "Result for hello"

    events = _read_events(temp_storage)
    assert len(events) == 1
    assert events[0]["kind"] == otel.KIND_AGENT
    assert events[0]["name"] == "test-agent"
    assert events[0]["status"] == otel.STATUS_OK
    assert events[0]["duration_ms"] > 0


def test_trace_agent_sync(temp_storage):
    @trace_agent(name="sync-agent")
    def my_agent(x: int) -> int:
        return x * 2

    result = my_agent(5)
    assert result == 10

    events = _read_events(temp_storage)
    assert len(events) == 1
    assert events[0]["name"] == "sync-agent"
    assert events[0]["status"] == otel.STATUS_OK


def test_trace_agent_captures_error(temp_storage):
    @trace_agent(name="failing-agent")
    def bad_agent():
        raise ValueError("Something broke")

    with pytest.raises(ValueError):
        bad_agent()

    events = _read_events(temp_storage)
    assert len(events) == 1
    assert events[0]["status"] == otel.STATUS_ERROR
    assert "Something broke" in events[0]["error"]


def test_trace_agent_default_name(temp_storage):
    @trace_agent()
    def my_cool_function():
        return "ok"

    my_cool_function()

    events = _read_events(temp_storage)
    assert events[0]["name"] == "my_cool_function"



def test_trace_agent_captures_input_output(temp_storage):
    @trace_agent(name="io-agent")
    def my_agent(query: str) -> str:
        return "The answer is 42"

    my_agent("What is the meaning of life?")

    events = _read_events(temp_storage)
    assert "meaning of life" in events[0]["input_preview"]
    assert "42" in events[0]["output_preview"]


@pytest.mark.asyncio
async def test_trace_llm_call_with_dict_result(temp_storage):
    @trace_llm_call(model="claude-sonnet-4-20250514")
    async def call_llm(prompt: str) -> dict:
        return {
            "content": "Hello world",
            "input_tokens": 100,
            "output_tokens": 50,
        }

    result = await call_llm("test prompt")
    assert result["content"] == "Hello world"

    events = _read_events(temp_storage)
    assert len(events) == 1
    assert events[0]["kind"] == otel.KIND_LLM
    assert events[0]["attributes"][otel.GEN_AI_REQUEST_MODEL] == "claude-sonnet-4-20250514"
    assert events[0]["attributes"][otel.GEN_AI_USAGE_INPUT_TOKENS] == 100
    assert events[0]["attributes"][otel.GEN_AI_USAGE_OUTPUT_TOKENS] == 50
    assert events[0]["attributes"][otel.AGENT_WATCH_COST_USD] > 0


def test_trace_llm_call_sync(temp_storage):
    @trace_llm_call(model="gpt-4o")
    def call_llm(prompt: str) -> dict:
        return {"content": "response", "input_tokens": 200, "output_tokens": 80}

    call_llm("test")

    events = _read_events(temp_storage)
    assert events[0]["attributes"][otel.GEN_AI_REQUEST_MODEL] == "gpt-4o"
    assert events[0]["attributes"][otel.AGENT_WATCH_COST_USD] > 0


@pytest.mark.asyncio
async def test_nested_traces(temp_storage):
    @trace_llm_call(model="claude-sonnet-4-20250514")
    async def inner_call(prompt: str) -> dict:
        return {"content": "result", "input_tokens": 50, "output_tokens": 25}

    @trace_agent(name="outer-agent")
    async def outer_agent(query: str) -> str:
        result = await inner_call(query)
        return result["content"]

    await outer_agent("test")

    events = _read_events(temp_storage)
    assert len(events) == 2

    # Find parent and child
    agent_event = next(e for e in events if e["kind"] == otel.KIND_AGENT)
    llm_event = next(e for e in events if e["kind"] == otel.KIND_LLM)

    assert llm_event["parent_span_id"] == agent_event["span_id"]
    assert llm_event["span_id"] in agent_event["children"]


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


def test_contextvars_restored_even_if_write_fails(temp_storage, monkeypatch):
    """If write_span raises during _finish_span, parent/trace contextvars must still be restored."""
    from agent_watch import collector

    @trace_agent(name="will-fail")
    def run():
        return "ok"

    def boom(_span):
        raise IOError("simulated disk failure")

    monkeypatch.setattr(collector, "write_span", boom)
    # decorator is wired before patching, so we also patch the module-local reference
    import agent_watch.decorators as dec
    monkeypatch.setattr(dec, "write_span", boom)

    with pytest.raises(IOError):
        run()

    # Both contextvars should be restored to their pre-run values (None in a clean test)
    assert collector.get_current_parent_id() is None
    assert collector.get_current_trace_id() is None

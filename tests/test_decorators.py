"""Tests for decorators."""

from __future__ import annotations

import json

import pytest

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
    assert events[0]["type"] == "agent_run"
    assert events[0]["name"] == "test-agent"
    assert events[0]["status"] == "success"
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
    assert events[0]["status"] == "success"


def test_trace_agent_captures_error(temp_storage):
    @trace_agent(name="failing-agent")
    def bad_agent():
        raise ValueError("Something broke")

    with pytest.raises(ValueError):
        bad_agent()

    events = _read_events(temp_storage)
    assert len(events) == 1
    assert events[0]["status"] == "error"
    assert "Something broke" in events[0]["error"]


def test_trace_agent_default_name(temp_storage):
    @trace_agent()
    def my_cool_function():
        return "ok"

    my_cool_function()

    events = _read_events(temp_storage)
    assert events[0]["name"] == "my_cool_function"


def test_trace_agent_with_tags(temp_storage):
    @trace_agent(name="tagged", tags=["prod", "v2"])
    def tagged_agent():
        return "ok"

    tagged_agent()

    events = _read_events(temp_storage)
    assert events[0]["metadata"]["tags"] == ["prod", "v2"]


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
    assert events[0]["type"] == "llm_call"
    assert events[0]["metadata"]["model"] == "claude-sonnet-4-20250514"
    assert events[0]["metadata"]["input_tokens"] == 100
    assert events[0]["metadata"]["output_tokens"] == 50
    assert events[0]["metadata"]["cost_usd"] > 0


def test_trace_llm_call_sync(temp_storage):
    @trace_llm_call(model="gpt-4o")
    def call_llm(prompt: str) -> dict:
        return {"content": "response", "input_tokens": 200, "output_tokens": 80}

    call_llm("test")

    events = _read_events(temp_storage)
    assert events[0]["metadata"]["model"] == "gpt-4o"
    assert events[0]["metadata"]["cost_usd"] > 0


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
    agent_event = next(e for e in events if e["type"] == "agent_run")
    llm_event = next(e for e in events if e["type"] == "llm_call")

    assert llm_event["parent_id"] == agent_event["id"]
    assert llm_event["id"] in agent_event["children"]

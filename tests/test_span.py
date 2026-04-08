"""Tests for Span context manager."""

from __future__ import annotations

import json

import pytest

from agent_watch.span import Span


def _read_events(storage_dir):
    events = []
    for f in storage_dir.glob("*.jsonl"):
        for line in open(f):
            events.append(json.loads(line))
    return events


def test_span_basic(temp_storage):
    with Span("data-processing") as span:
        result = 1 + 1

    events = _read_events(temp_storage)
    assert len(events) == 1
    assert events[0]["type"] == "span"
    assert events[0]["name"] == "data-processing"
    assert events[0]["status"] == "success"
    assert events[0]["duration_ms"] > 0


def test_span_captures_error(temp_storage):
    with pytest.raises(ValueError):
        with Span("failing-span"):
            raise ValueError("oops")

    events = _read_events(temp_storage)
    assert events[0]["status"] == "error"
    assert "oops" in events[0]["error"]


def test_span_metadata(temp_storage):
    with Span("custom-span") as span:
        span.set_metadata("rows", 100)
        span.set_metadata("source", "database")

    events = _read_events(temp_storage)
    assert events[0]["metadata"]["rows"] == 100
    assert events[0]["metadata"]["source"] == "database"


def test_span_input_output(temp_storage):
    with Span("io-span") as span:
        span.set_input("input data")
        span.set_output("output data")

    events = _read_events(temp_storage)
    assert events[0]["input_preview"] == "input data"
    assert events[0]["output_preview"] == "output data"


def test_span_with_tags(temp_storage):
    with Span("tagged", tags=["test", "v1"]):
        pass

    events = _read_events(temp_storage)
    assert events[0]["metadata"]["tags"] == ["test", "v1"]


@pytest.mark.asyncio
async def test_span_async(temp_storage):
    async with Span("async-span") as span:
        span.set_metadata("async", True)

    events = _read_events(temp_storage)
    assert events[0]["name"] == "async-span"
    assert events[0]["metadata"]["async"] is True


def test_nested_spans(temp_storage):
    with Span("outer") as outer:
        with Span("inner") as inner:
            pass

    events = _read_events(temp_storage)
    assert len(events) == 2

    inner_event = next(e for e in events if e["name"] == "inner")
    outer_event = next(e for e in events if e["name"] == "outer")

    assert inner_event["parent_id"] == outer_event["id"]

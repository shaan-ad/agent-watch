"""Tests for the event collector."""

from __future__ import annotations

import json

from agent_watch.collector import (
    get_current_parent_id,
    get_storage_dir,
    get_today_file,
    set_current_parent_id,
    write_event,
)
from agent_watch.types import Event


def test_storage_dir_created(temp_storage):
    d = get_storage_dir()
    assert d.exists()


def test_today_file_path(temp_storage):
    f = get_today_file()
    assert f.suffix == ".jsonl"
    # Should contain today's date
    assert len(f.stem) == 10  # YYYY-MM-DD


def test_write_event(temp_storage):
    event = Event(type="test", name="test-event")
    event.finish()
    write_event(event)

    filepath = get_today_file()
    assert filepath.exists()

    with open(filepath) as f:
        lines = f.readlines()
    assert len(lines) == 1

    data = json.loads(lines[0])
    assert data["name"] == "test-event"
    assert data["type"] == "test"


def test_write_multiple_events(temp_storage):
    for i in range(5):
        event = Event(type="test", name=f"event-{i}")
        event.finish()
        write_event(event)

    filepath = get_today_file()
    with open(filepath) as f:
        lines = f.readlines()
    assert len(lines) == 5


def test_parent_id_context():
    # Initially None
    assert get_current_parent_id() is None

    # Set a parent
    prev = set_current_parent_id("parent-1")
    assert prev is None
    assert get_current_parent_id() == "parent-1"

    # Nest another parent
    prev = set_current_parent_id("parent-2")
    assert prev == "parent-1"
    assert get_current_parent_id() == "parent-2"

    # Restore
    set_current_parent_id(prev)
    assert get_current_parent_id() == "parent-1"

    # Clear
    set_current_parent_id(None)
    assert get_current_parent_id() is None

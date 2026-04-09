"""Event collector: captures events and writes to JSONL files."""

from __future__ import annotations

import contextvars
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from agent_watch.types import Event

# Context variables for span tracking (works with both threads and async)
_parent_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "agent_watch_parent_id", default=None
)
_children_var: contextvars.ContextVar[Dict[str, List[str]]] = contextvars.ContextVar(
    "agent_watch_children", default={}
)

# Default storage directory
DEFAULT_DIR = ".agent-watch"


def get_storage_dir() -> Path:
    """Get the storage directory, creating it if needed."""
    dir_path = Path(os.environ.get("AGENT_WATCH_DIR", DEFAULT_DIR))
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_today_file() -> Path:
    """Get the JSONL file path for today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return get_storage_dir() / f"{today}.jsonl"


def write_event(event: Event) -> None:
    """Append an event to today's JSONL file."""
    filepath = get_today_file()
    line = event.to_json() + "\n"
    with open(filepath, "a") as f:
        f.write(line)


def get_current_parent_id() -> Optional[str]:
    """Get the current parent span ID from context."""
    return _parent_id_var.get()


def set_current_parent_id(parent_id: Optional[str]) -> Optional[str]:
    """Set the current parent span ID. Returns the previous value."""
    previous = _parent_id_var.get()
    _parent_id_var.set(parent_id)
    return previous


def add_child_to_parent(parent_id: str, child_id: str) -> None:
    """Record a child event under its parent.

    This is tracked in memory. When the parent event is written,
    its children list will include this child.
    """
    children = _children_var.get()
    # Copy-on-write to avoid mutating shared default
    if parent_id not in children:
        children = {**children, parent_id: []}
    else:
        children = {**children, parent_id: list(children[parent_id])}
    children[parent_id].append(child_id)
    _children_var.set(children)


def get_children(parent_id: str) -> List[str]:
    """Get child IDs for a parent."""
    children = _children_var.get()
    return children.get(parent_id, [])

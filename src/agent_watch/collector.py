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
    """Get the storage directory, creating it if needed."""
    dir_path = Path(os.environ.get("AGENT_WATCH_DIR", DEFAULT_DIR))
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_today_file() -> Path:
    """Get the JSONL file path for today (UTC)."""
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
    """Get the current parent span ID from context."""
    return _parent_span_id_var.get()


def set_current_parent_id(parent_id: Optional[str]) -> Optional[str]:
    """Set the current parent span ID. Returns the previous value."""
    previous = _parent_span_id_var.get()
    _parent_span_id_var.set(parent_id)
    return previous


def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID from context."""
    return _trace_id_var.get()


def set_current_trace_id(trace_id: Optional[str]) -> Optional[str]:
    """Set the current trace ID. Returns the previous value."""
    previous = _trace_id_var.get()
    _trace_id_var.set(trace_id)
    return previous


def add_child_to_parent(parent_id: str, child_id: str) -> None:
    """Record a child span under its parent (in-memory context)."""
    children = _children_var.get()
    if parent_id not in children:
        children = {**children, parent_id: []}
    else:
        children = {**children, parent_id: list(children[parent_id])}
    children[parent_id].append(child_id)
    _children_var.set(children)


def get_children(parent_id: str) -> List[str]:
    """Get child span IDs for a parent."""
    children = _children_var.get()
    return children.get(parent_id, [])

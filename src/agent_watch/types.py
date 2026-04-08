"""Event types for agent telemetry."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Event:
    """Base telemetry event."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "span"
    name: str = ""
    parent_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    duration_ms: float = 0.0
    status: str = "success"  # "success" or "error"
    error: Optional[str] = None
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)

    def finish(self, status: str = "success", error: Optional[str] = None) -> None:
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
    def from_dict(cls, data: Dict[str, Any]) -> Event:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, line: str) -> Event:
        return cls.from_dict(json.loads(line))


def make_agent_event(
    name: str,
    parent_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Event:
    """Create an agent_run event."""
    event = Event(type="agent_run", name=name, parent_id=parent_id)
    if tags:
        event.metadata["tags"] = tags
    return event


def make_llm_event(
    name: str,
    model: str,
    parent_id: Optional[str] = None,
) -> Event:
    """Create an llm_call event."""
    event = Event(type="llm_call", name=name, parent_id=parent_id)
    event.metadata["model"] = model
    return event


def make_span_event(
    name: str,
    parent_id: Optional[str] = None,
) -> Event:
    """Create a generic span event."""
    return Event(type="span", name=name, parent_id=parent_id)


def preview(value: Any, max_len: int = 200) -> Optional[str]:
    """Create a preview string from any value."""
    if value is None:
        return None
    s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s

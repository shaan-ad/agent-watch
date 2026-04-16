"""Span types for agent telemetry, aligned with OpenTelemetry GenAI conventions."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from agent_watch import otel


@dataclass
class Span:
    """Telemetry span, OTel GenAI-aligned.

    Attributes use OTel semantic convention keys (see ``agent_watch.otel``).
    Serialization emits a ``schema`` field so readers can detect format.
    """

    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: Optional[str] = None
    kind: str = otel.KIND_SPAN
    name: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    duration_ms: float = 0.0
    status: str = otel.STATUS_OK
    error: Optional[str] = None
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)
    schema: str = otel.SCHEMA_VERSION

    def finish(self, status: str = otel.STATUS_OK, error: Optional[str] = None) -> None:
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
    def from_dict(cls, data: Dict[str, Any]) -> Span:
        if not data:
            raise ValueError("Cannot deserialize empty dict into Span")
        if "schema" in data:
            if data["schema"] == otel.SCHEMA_VERSION:
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            raise ValueError(f"Unknown schema version: {data['schema']!r}")
        return _from_legacy_v01(data)

    @classmethod
    def from_json(cls, line: str) -> Span:
        return cls.from_dict(json.loads(line))


# Deprecated alias for v0.1 compatibility. Will be removed in v2.0.
Event = Span


_LEGACY_TYPE_TO_KIND = {
    "agent_run": otel.KIND_AGENT,
    "llm_call": otel.KIND_LLM,
    "span": otel.KIND_SPAN,
}

_LEGACY_STATUS = {
    "success": otel.STATUS_OK,
    "error": otel.STATUS_ERROR,
}

_LEGACY_METADATA_REMAP = {
    "model": otel.GEN_AI_REQUEST_MODEL,
    "input_tokens": otel.GEN_AI_USAGE_INPUT_TOKENS,
    "output_tokens": otel.GEN_AI_USAGE_OUTPUT_TOKENS,
    "cost_usd": otel.AGENT_WATCH_COST_USD,
    "tags": otel.AGENT_WATCH_TAGS,
}


def _from_legacy_v01(data: Dict[str, Any]) -> Span:
    """Translate a v0.1 Event dict into a v1.0 Span."""
    legacy_metadata = data.get("metadata", {}) or {}
    attributes: Dict[str, Any] = {}
    for legacy_key, value in legacy_metadata.items():
        attributes[_LEGACY_METADATA_REMAP.get(legacy_key, legacy_key)] = value

    legacy_id = data.get("id", "")
    return Span(
        span_id=legacy_id,
        trace_id=legacy_id,  # synthesize: legacy spans are their own trace root
        parent_span_id=data.get("parent_id"),
        kind=_LEGACY_TYPE_TO_KIND.get(data.get("type", "span"), otel.KIND_SPAN),
        name=data.get("name", ""),
        start_time=data.get("start_time", 0.0),
        end_time=data.get("end_time", 0.0),
        duration_ms=data.get("duration_ms", 0.0),
        status=_LEGACY_STATUS.get(data.get("status", "success"), otel.STATUS_OK),
        error=data.get("error"),
        input_preview=data.get("input_preview"),
        output_preview=data.get("output_preview"),
        attributes=attributes,
        children=list(data.get("children", []) or []),
        schema=otel.SCHEMA_VERSION,
    )


def make_agent_span(
    name: str,
    parent_span_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Span:
    """Create an agent-kind span."""
    span = Span(kind=otel.KIND_AGENT, name=name, parent_span_id=parent_span_id)
    if trace_id:
        span.trace_id = trace_id
    if tags:
        span.attributes[otel.AGENT_WATCH_TAGS] = tags
    return span


def make_llm_span(
    name: str,
    model: str = "",
    parent_span_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Span:
    """Create an llm-kind span."""
    span = Span(kind=otel.KIND_LLM, name=name, parent_span_id=parent_span_id)
    if trace_id:
        span.trace_id = trace_id
    if model:
        span.attributes[otel.GEN_AI_REQUEST_MODEL] = model
    return span


def make_generic_span(
    name: str,
    parent_span_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Span:
    """Create a generic span."""
    span = Span(kind=otel.KIND_SPAN, name=name, parent_span_id=parent_span_id)
    if trace_id:
        span.trace_id = trace_id
    return span


# --- Legacy helper aliases (for any code still using v0.1 names) ---
make_agent_event = make_agent_span
make_llm_event = make_llm_span
make_span_event = make_generic_span


def preview(value: Any, max_len: int = 200) -> Optional[str]:
    """Create a preview string from any value."""
    if value is None:
        return None
    s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s

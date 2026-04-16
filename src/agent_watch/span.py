"""Span context manager for custom instrumentation.

Note: the context manager class is ``Span`` (this file). The telemetry
dataclass is also named ``Span`` but lives in ``agent_watch.types``. We
alias the dataclass as ``_SpanRecord`` here to avoid name collision at
the module level.
"""

from __future__ import annotations

import uuid
from typing import Any, List, Optional

from agent_watch import otel
from agent_watch.collector import (
    add_child_to_parent,
    get_children,
    get_current_parent_id,
    get_current_trace_id,
    set_current_parent_id,
    set_current_trace_id,
    write_span,
)
from agent_watch.types import Span as _SpanRecord
from agent_watch.types import make_generic_span, preview


class Span:
    """Context manager for instrumenting any block of code.

    Usage:
        with Span("data-processing") as span:
            result = process_data(data)
            span.set_metadata("rows", len(data))

        # Async usage:
        async with Span("api-call") as span:
            result = await fetch_data()
    """

    def __init__(
        self,
        name: str,
        tags: Optional[List[str]] = None,
    ):
        self.name = name
        self.tags = tags
        self._span: Optional[_SpanRecord] = None
        self._previous_parent: Optional[str] = None
        self._previous_trace: Optional[str] = None

    def _start(self) -> "Span":
        parent_id = get_current_parent_id()
        trace_id = get_current_trace_id() or str(uuid.uuid4())
        self._span = make_generic_span(name=self.name, parent_span_id=parent_id, trace_id=trace_id)
        if self.tags:
            self._span.attributes[otel.AGENT_WATCH_TAGS] = self.tags
        self._previous_parent = set_current_parent_id(self._span.span_id)
        self._previous_trace = set_current_trace_id(trace_id)
        if parent_id:
            add_child_to_parent(parent_id, self._span.span_id)
        return self

    def _finish(self, error: Optional[str] = None) -> None:
        if self._span is None:
            return
        status = otel.STATUS_ERROR if error else otel.STATUS_OK
        self._span.children = get_children(self._span.span_id)
        self._span.finish(status=status, error=error)
        try:
            write_span(self._span)
        finally:
            set_current_parent_id(self._previous_parent)
            set_current_trace_id(self._previous_trace)

    def set_metadata(self, key: str, value: Any) -> None:
        """Add an attribute to this span (named set_metadata for v0.1 API compat)."""
        if self._span:
            self._span.attributes[key] = value

    def set_attribute(self, key: str, value: Any) -> None:
        """Add an attribute to this span."""
        self.set_metadata(key, value)

    def set_input(self, value: Any) -> None:
        """Set the input preview for this span."""
        if self._span:
            self._span.input_preview = preview(value)

    def set_output(self, value: Any) -> None:
        """Set the output preview for this span."""
        if self._span:
            self._span.output_preview = preview(value)

    @property
    def span_id(self) -> Optional[str]:
        return self._span.span_id if self._span else None

    @property
    def event_id(self) -> Optional[str]:
        """Deprecated: use span_id."""
        return self.span_id

    def __enter__(self) -> "Span":
        return self._start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        error = str(exc_val) if exc_val else None
        self._finish(error=error)

    async def __aenter__(self) -> "Span":
        return self._start()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        error = str(exc_val) if exc_val else None
        self._finish(error=error)

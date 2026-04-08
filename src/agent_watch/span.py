"""Span context manager for custom instrumentation."""

from __future__ import annotations

from typing import Any, List, Optional

from agent_watch.collector import (
    add_child_to_parent,
    get_children,
    get_current_parent_id,
    set_current_parent_id,
    write_event,
)
from agent_watch.types import Event, make_span_event, preview


class Span:
    """Context manager for instrumenting any block of code.

    Usage:
        with Span("data-processing") as span:
            result = process_data(data)
            span.set_metadata("rows_processed", len(data))

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
        self._event: Optional[Event] = None
        self._previous_parent: Optional[str] = None

    def _start(self) -> "Span":
        parent_id = get_current_parent_id()
        self._event = make_span_event(name=self.name, parent_id=parent_id)
        if self.tags:
            self._event.metadata["tags"] = self.tags

        # Set this span as the current parent for nested spans
        self._previous_parent = set_current_parent_id(self._event.id)

        # Register as child of parent
        if parent_id:
            add_child_to_parent(parent_id, self._event.id)

        return self

    def _finish(self, error: Optional[str] = None) -> None:
        if self._event is None:
            return

        status = "error" if error else "success"
        self._event.children = get_children(self._event.id)
        self._event.finish(status=status, error=error)
        write_event(self._event)

        # Restore previous parent context
        set_current_parent_id(self._previous_parent)

    def set_metadata(self, key: str, value: Any) -> None:
        """Add metadata to this span."""
        if self._event:
            self._event.metadata[key] = value

    def set_input(self, value: Any) -> None:
        """Set the input preview for this span."""
        if self._event:
            self._event.input_preview = preview(value)

    def set_output(self, value: Any) -> None:
        """Set the output preview for this span."""
        if self._event:
            self._event.output_preview = preview(value)

    @property
    def event_id(self) -> Optional[str]:
        return self._event.id if self._event else None

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

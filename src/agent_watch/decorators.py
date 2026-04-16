"""Decorators for tracing agent functions and LLM calls."""

from __future__ import annotations

import functools
import inspect
import uuid
from typing import Any, Callable, List, Optional

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
from agent_watch.cost import estimate_cost
from agent_watch.types import Span, make_agent_span, make_llm_span, preview


def trace_agent(
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Callable:
    """Trace an agent function (sync or async)."""

    def decorator(func: Callable) -> Callable:
        agent_name = name or func.__name__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                return await _run_agent_async(func, agent_name, tags, args, kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return _run_agent_sync(func, agent_name, tags, args, kwargs)

        return sync_wrapper

    return decorator


def trace_llm_call(
    model: str = "",
    name: Optional[str] = None,
) -> Callable:
    """Trace an LLM call. Decorated function returns a dict with content/input_tokens/output_tokens."""

    def decorator(func: Callable) -> Callable:
        call_name = name or func.__name__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                return await _run_llm_async(func, call_name, model, args, kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return _run_llm_sync(func, call_name, model, args, kwargs)

        return sync_wrapper

    return decorator


# --- internal helpers ---

def _start_agent_span(agent_name: str, tags: Optional[List[str]]) -> tuple[Span, Optional[str], Optional[str]]:
    parent_id = get_current_parent_id()
    trace_id = get_current_trace_id() or str(uuid.uuid4())
    span = make_agent_span(agent_name, parent_span_id=parent_id, trace_id=trace_id, tags=tags)
    if parent_id:
        add_child_to_parent(parent_id, span.span_id)
    previous_parent = set_current_parent_id(span.span_id)
    previous_trace = set_current_trace_id(trace_id)
    return span, previous_parent, previous_trace


def _start_llm_span(call_name: str, model: str) -> tuple[Span, Optional[str], Optional[str]]:
    parent_id = get_current_parent_id()
    trace_id = get_current_trace_id() or str(uuid.uuid4())
    span = make_llm_span(call_name, model=model, parent_span_id=parent_id, trace_id=trace_id)
    if parent_id:
        add_child_to_parent(parent_id, span.span_id)
    previous_parent = set_current_parent_id(span.span_id)
    previous_trace = set_current_trace_id(trace_id)
    return span, previous_parent, previous_trace


def _finish_span(
    span: Span,
    previous_parent: Optional[str],
    previous_trace: Optional[str],
    status: str,
    error: Optional[str],
) -> None:
    span.children = get_children(span.span_id)
    span.finish(status=status, error=error)
    try:
        write_span(span)
    finally:
        set_current_parent_id(previous_parent)
        set_current_trace_id(previous_trace)


async def _run_agent_async(func: Callable, agent_name: str, tags, args, kwargs) -> Any:
    span, prev_parent, prev_trace = _start_agent_span(agent_name, tags)
    span.input_preview = preview(_format_args(args, kwargs))
    try:
        result = await func(*args, **kwargs)
        span.output_preview = preview(result)
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_OK, None)
        return result
    except Exception as e:
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise


def _run_agent_sync(func: Callable, agent_name: str, tags, args, kwargs) -> Any:
    span, prev_parent, prev_trace = _start_agent_span(agent_name, tags)
    span.input_preview = preview(_format_args(args, kwargs))
    try:
        result = func(*args, **kwargs)
        span.output_preview = preview(result)
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_OK, None)
        return result
    except Exception as e:
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise


async def _run_llm_async(func: Callable, call_name: str, model: str, args, kwargs) -> Any:
    span, prev_parent, prev_trace = _start_llm_span(call_name, model)
    span.input_preview = preview(_format_args(args, kwargs))
    try:
        result = await func(*args, **kwargs)
        _extract_llm_attributes(span, result, model)
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_OK, None)
        return result
    except Exception as e:
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise


def _run_llm_sync(func: Callable, call_name: str, model: str, args, kwargs) -> Any:
    span, prev_parent, prev_trace = _start_llm_span(call_name, model)
    span.input_preview = preview(_format_args(args, kwargs))
    try:
        result = func(*args, **kwargs)
        _extract_llm_attributes(span, result, model)
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_OK, None)
        return result
    except Exception as e:
        _finish_span(span, prev_parent, prev_trace, otel.STATUS_ERROR, str(e))
        raise


def _extract_llm_attributes(span: Span, result: Any, model: str) -> None:
    input_tokens = 0
    output_tokens = 0
    content = ""

    if isinstance(result, dict):
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        content = result.get("content", "")
    elif hasattr(result, "input_tokens"):
        input_tokens = getattr(result, "input_tokens", 0)
        output_tokens = getattr(result, "output_tokens", 0)
        content = getattr(result, "content", "")
    elif isinstance(result, str):
        content = result

    if input_tokens or output_tokens:
        span.attributes[otel.GEN_AI_USAGE_INPUT_TOKENS] = input_tokens
        span.attributes[otel.GEN_AI_USAGE_OUTPUT_TOKENS] = output_tokens
    span.output_preview = preview(content)

    if model and (input_tokens or output_tokens):
        cost = estimate_cost(model, input_tokens, output_tokens)
        if cost is not None:
            span.attributes[otel.AGENT_WATCH_COST_USD] = cost


def _format_args(args: tuple, kwargs: dict) -> str:
    parts = [str(a) for a in args]
    parts.extend(f"{k}={v}" for k, v in kwargs.items())
    return ", ".join(parts)

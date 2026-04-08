"""Decorators for tracing agent functions and LLM calls."""

from __future__ import annotations

import asyncio
import functools
import inspect
from typing import Any, Callable, List, Optional

from agent_watch.collector import (
    add_child_to_parent,
    get_children,
    get_current_parent_id,
    set_current_parent_id,
    write_event,
)
from agent_watch.cost import estimate_cost
from agent_watch.types import Event, make_agent_event, make_llm_event, preview


def trace_agent(
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Callable:
    """Decorator that traces an agent function.

    Works with both sync and async functions. Captures inputs, outputs,
    duration, and success/failure.

    Usage:
        @trace_agent(name="research-agent")
        async def research(topic: str) -> str:
            ...

        @trace_agent()
        def simple_agent(query: str) -> str:
            ...
    """

    def decorator(func: Callable) -> Callable:
        agent_name = name or func.__name__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                parent_id = get_current_parent_id()
                event = make_agent_event(agent_name, parent_id=parent_id, tags=tags)
                event.input_preview = preview(_format_args(args, kwargs))

                # Register as child of parent
                if parent_id:
                    add_child_to_parent(parent_id, event.id)

                # Set as current parent for nested traces
                previous_parent = set_current_parent_id(event.id)

                try:
                    result = await func(*args, **kwargs)
                    event.output_preview = preview(result)
                    event.children = get_children(event.id)
                    event.finish(status="success")
                    write_event(event)
                    return result
                except Exception as e:
                    event.children = get_children(event.id)
                    event.finish(status="error", error=str(e))
                    write_event(event)
                    raise
                finally:
                    set_current_parent_id(previous_parent)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                parent_id = get_current_parent_id()
                event = make_agent_event(agent_name, parent_id=parent_id, tags=tags)
                event.input_preview = preview(_format_args(args, kwargs))

                if parent_id:
                    add_child_to_parent(parent_id, event.id)

                previous_parent = set_current_parent_id(event.id)

                try:
                    result = func(*args, **kwargs)
                    event.output_preview = preview(result)
                    event.children = get_children(event.id)
                    event.finish(status="success")
                    write_event(event)
                    return result
                except Exception as e:
                    event.children = get_children(event.id)
                    event.finish(status="error", error=str(e))
                    write_event(event)
                    raise
                finally:
                    set_current_parent_id(previous_parent)

            return sync_wrapper

    return decorator


def trace_llm_call(
    model: str = "",
    name: Optional[str] = None,
) -> Callable:
    """Decorator that traces an LLM call.

    Captures model, tokens, cost, and latency. The decorated function
    should return a dict with 'content', 'input_tokens', and 'output_tokens'
    keys, or any object with those attributes. If it returns a plain string,
    only the output is captured.

    Usage:
        @trace_llm_call(model="claude-sonnet-4-20250514")
        async def call_claude(prompt: str) -> dict:
            response = await client.messages.create(...)
            return {
                "content": response.content[0].text,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
    """

    def decorator(func: Callable) -> Callable:
        call_name = name or func.__name__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                parent_id = get_current_parent_id()
                event = make_llm_event(call_name, model=model, parent_id=parent_id)
                event.input_preview = preview(_format_args(args, kwargs))

                if parent_id:
                    add_child_to_parent(parent_id, event.id)

                previous_parent = set_current_parent_id(event.id)

                try:
                    result = await func(*args, **kwargs)
                    _extract_llm_metadata(event, result, model)
                    event.children = get_children(event.id)
                    event.finish(status="success")
                    write_event(event)
                    return result
                except Exception as e:
                    event.children = get_children(event.id)
                    event.finish(status="error", error=str(e))
                    write_event(event)
                    raise
                finally:
                    set_current_parent_id(previous_parent)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                parent_id = get_current_parent_id()
                event = make_llm_event(call_name, model=model, parent_id=parent_id)
                event.input_preview = preview(_format_args(args, kwargs))

                if parent_id:
                    add_child_to_parent(parent_id, event.id)

                previous_parent = set_current_parent_id(event.id)

                try:
                    result = func(*args, **kwargs)
                    _extract_llm_metadata(event, result, model)
                    event.children = get_children(event.id)
                    event.finish(status="success")
                    write_event(event)
                    return result
                except Exception as e:
                    event.children = get_children(event.id)
                    event.finish(status="error", error=str(e))
                    write_event(event)
                    raise
                finally:
                    set_current_parent_id(previous_parent)

            return sync_wrapper

    return decorator


def _extract_llm_metadata(event: Event, result: Any, model: str) -> None:
    """Extract token counts and cost from an LLM call result."""
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

    event.metadata["input_tokens"] = input_tokens
    event.metadata["output_tokens"] = output_tokens
    event.output_preview = preview(content)

    if model and (input_tokens or output_tokens):
        cost = estimate_cost(model, input_tokens, output_tokens)
        if cost is not None:
            event.metadata["cost_usd"] = cost


def _format_args(args: tuple, kwargs: dict) -> str:
    """Format function arguments for preview."""
    parts = [str(a) for a in args]
    parts.extend(f"{k}={v}" for k, v in kwargs.items())
    return ", ".join(parts)

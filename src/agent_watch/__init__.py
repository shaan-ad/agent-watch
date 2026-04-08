"""Agent Watch: observability for AI agents."""

__version__ = "0.1.0"

from agent_watch.decorators import trace_agent, trace_llm_call
from agent_watch.span import Span
from agent_watch.types import Event

__all__ = ["trace_agent", "trace_llm_call", "Span", "Event"]

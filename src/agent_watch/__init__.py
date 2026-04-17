"""Agent Watch: observability and cost enforcement for AI agents."""

__version__ = "1.0.0.dev0"

from agent_watch.budget import BudgetExceeded
from agent_watch.decorators import trace_agent, trace_llm_call
from agent_watch.span import Span  # context manager
from agent_watch.types import Span as SpanRecord  # dataclass (for exporters, advanced use)

# v0.1 deprecated alias
Event = SpanRecord

__all__ = [
    "trace_agent",
    "trace_llm_call",
    "Span",
    "SpanRecord",
    "Event",
    "BudgetExceeded",
]

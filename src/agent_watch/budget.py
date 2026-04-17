"""Budget enforcement primitives.

A Budget is a running USD cap scoped to a tracing context. Decorators push a
Budget onto the stack when a trace_agent has a budget_usd kwarg or when
AGENT_WATCH_BUDGET_USD is set. Each traced LLM call calls Budget.add_spend(cost)
and Budget.check() after cost is computed. If check() finds the active budget
over its cap, it raises BudgetExceeded, which propagates out of the LLM call
and stops any subsequent calls in the loop.
"""

from __future__ import annotations

import contextvars
import os
from typing import List, Literal, Optional


class BudgetExceeded(RuntimeError):
    """Raised when a tracing context exceeds its USD budget cap."""

    def __init__(self, spent_usd: float, budget_usd: float, agent_name: str):
        self.spent_usd = spent_usd
        self.budget_usd = budget_usd
        self.agent_name = agent_name
        super().__init__(
            f"Budget exceeded for '{agent_name}': spent ${spent_usd:.2f} of ${budget_usd:.2f}"
        )


class Budget:
    """A USD cap plus running spend for a tracing context."""

    def __init__(
        self,
        cap_usd: float,
        agent_name: str = "",
        on_exceed: Literal["raise", "warn"] = "raise",
    ):
        self.cap_usd = cap_usd
        self.agent_name = agent_name
        self.on_exceed = on_exceed
        self.spent_usd = 0.0
        self._exceeded = False

    def add_spend(self, cost_usd: float) -> None:
        if cost_usd and cost_usd > 0:
            self.spent_usd += cost_usd
            if self.spent_usd > self.cap_usd:
                self._exceeded = True

    def is_exceeded(self) -> bool:
        return self._exceeded

    def check(self) -> None:
        if self._exceeded and self.on_exceed == "raise":
            raise BudgetExceeded(
                spent_usd=self.spent_usd,
                budget_usd=self.cap_usd,
                agent_name=self.agent_name,
            )


# Stack of active budgets. Nested agents push/pop.
_budget_stack_var: contextvars.ContextVar[List[Budget]] = contextvars.ContextVar(
    "agent_watch_budget_stack", default=[]
)


def push_budget(budget: Budget) -> List[Budget]:
    """Push a budget onto the context stack. Returns the previous stack for restoration."""
    current = list(_budget_stack_var.get())
    previous = current
    current.append(budget)
    _budget_stack_var.set(current)
    return previous


def pop_budget(previous: List[Budget]) -> None:
    """Restore the budget stack to a previous state."""
    _budget_stack_var.set(previous)


def active_budgets() -> List[Budget]:
    """Return a copy of the currently active budget stack."""
    return list(_budget_stack_var.get())


def record_spend(cost_usd: float) -> None:
    """Add spend to every budget currently on the stack (parent budgets see child spend)."""
    for b in _budget_stack_var.get():
        b.add_spend(cost_usd)


def check_all_budgets() -> None:
    """Raise BudgetExceeded if any active budget is over its cap in 'raise' mode.

    Checks outermost first so that when a nested call exceeds a parent budget,
    the parent's error is what the user sees.
    """
    for b in _budget_stack_var.get():
        b.check()


def get_env_budget_cap_usd() -> Optional[float]:
    """Read AGENT_WATCH_BUDGET_USD env var as a float cap, or return None."""
    value = os.environ.get("AGENT_WATCH_BUDGET_USD")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None

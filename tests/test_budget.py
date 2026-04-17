"""Tests for budget enforcement."""

import pytest
from agent_watch.budget import Budget, BudgetExceeded


def test_budget_exceeded_has_diagnostic_fields():
    err = BudgetExceeded(spent_usd=5.50, budget_usd=5.00, agent_name="loop")
    assert err.spent_usd == 5.50
    assert err.budget_usd == 5.00
    assert err.agent_name == "loop"
    assert "5.50" in str(err)
    assert "5.00" in str(err)
    assert "loop" in str(err)


def test_budget_tracks_spend():
    b = Budget(cap_usd=10.0, agent_name="x")
    assert b.spent_usd == 0.0
    b.add_spend(1.50)
    b.add_spend(0.75)
    assert b.spent_usd == pytest.approx(2.25)


def test_budget_under_cap_does_not_raise():
    b = Budget(cap_usd=5.0, agent_name="x")
    b.add_spend(1.0)
    b.check()  # should not raise


def test_budget_over_cap_raises():
    b = Budget(cap_usd=5.0, agent_name="y")
    b.add_spend(3.0)
    b.add_spend(2.5)
    with pytest.raises(BudgetExceeded) as exc_info:
        b.check()
    assert exc_info.value.spent_usd == pytest.approx(5.5)
    assert exc_info.value.budget_usd == 5.0
    assert exc_info.value.agent_name == "y"


def test_budget_warn_mode_does_not_raise():
    b = Budget(cap_usd=5.0, agent_name="z", on_exceed="warn")
    b.add_spend(10.0)
    b.check()  # must not raise


def test_budget_exceeded_flag():
    b = Budget(cap_usd=5.0, agent_name="x")
    assert not b.is_exceeded()
    b.add_spend(10.0)
    assert b.is_exceeded()


def test_push_pop_budget_restores_stack():
    """pop_budget must restore the exact pre-push state."""
    from agent_watch.budget import active_budgets, pop_budget, push_budget

    assert active_budgets() == []

    b1 = Budget(cap_usd=10.0, agent_name="outer")
    prev = push_budget(b1)
    assert len(active_budgets()) == 1
    assert active_budgets()[0] is b1

    b2 = Budget(cap_usd=5.0, agent_name="inner")
    prev2 = push_budget(b2)
    assert len(active_budgets()) == 2

    pop_budget(prev2)
    assert len(active_budgets()) == 1
    assert active_budgets()[0] is b1

    pop_budget(prev)
    assert active_budgets() == []


def test_record_spend_across_nested_budgets():
    """record_spend adds to every budget on the stack."""
    from agent_watch.budget import pop_budget, push_budget, record_spend

    outer = Budget(cap_usd=100.0, agent_name="outer")
    inner = Budget(cap_usd=10.0, agent_name="inner")
    prev_outer = push_budget(outer)
    prev_inner = push_budget(inner)

    record_spend(2.5)
    assert outer.spent_usd == pytest.approx(2.5)
    assert inner.spent_usd == pytest.approx(2.5)

    pop_budget(prev_inner)
    pop_budget(prev_outer)


import asyncio

from agent_watch import trace_agent, trace_llm_call
from agent_watch.budget import BudgetExceeded


def test_trace_agent_with_budget_under_cap_does_not_raise(temp_storage):
    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        return {"content": "ok", "input_tokens": 100, "output_tokens": 50}

    @trace_agent(name="cheap", budget_usd=10.0)
    def run():
        return call("hi")

    result = run()
    assert result["content"] == "ok"


def test_trace_agent_raises_budget_exceeded_after_over_cap_call(temp_storage):
    """Single over-cap call: the call fires, but the decorator raises on exit."""
    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        # gpt-4o: 100 * 2.50/1M + 50 * 10/1M = $0.00075 per call
        return {"content": "x", "input_tokens": 100, "output_tokens": 50}

    @trace_agent(name="tight", budget_usd=0.0001)  # cap below single-call cost
    def run():
        return call("hi")

    with pytest.raises(BudgetExceeded) as exc_info:
        run()
    assert exc_info.value.agent_name == "tight"
    assert exc_info.value.budget_usd == 0.0001
    assert exc_info.value.spent_usd > 0.0001


def test_trace_agent_budget_stops_second_call_in_loop(temp_storage):
    """After first over-cap call, next call is not made because exception propagated."""
    call_count = {"n": 0}

    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        call_count["n"] += 1
        return {"content": "x", "input_tokens": 1000, "output_tokens": 500}

    @trace_agent(name="loop", budget_usd=0.0001)
    def run():
        for i in range(10):
            call(f"turn {i}")
        return "done"

    with pytest.raises(BudgetExceeded):
        run()
    assert call_count["n"] == 1  # second call never fires


def test_trace_agent_budget_warn_mode_does_not_raise(temp_storage):
    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        return {"content": "x", "input_tokens": 1000, "output_tokens": 500}

    @trace_agent(name="warner", budget_usd=0.0001, on_exceed="warn")
    def run():
        for i in range(3):
            call(f"turn {i}")
        return "done"

    result = run()  # must not raise
    assert result == "done"


@pytest.mark.asyncio
async def test_trace_agent_budget_async(temp_storage):
    @trace_llm_call(model="gpt-4o")
    async def call(p: str) -> dict:
        return {"content": "x", "input_tokens": 10000, "output_tokens": 5000}

    @trace_agent(name="a", budget_usd=0.0001)
    async def run():
        await call("x")
        await call("y")
        return "done"

    with pytest.raises(BudgetExceeded):
        await run()


def test_env_budget_cap(temp_storage, monkeypatch):
    monkeypatch.setenv("AGENT_WATCH_BUDGET_USD", "0.0001")

    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        return {"content": "x", "input_tokens": 1000, "output_tokens": 500}

    @trace_agent(name="env")
    def run():
        for i in range(5):
            call(f"turn {i}")

    with pytest.raises(BudgetExceeded):
        run()


def test_nested_agents_both_budgets_count_spend(temp_storage):
    """Parent and child budgets both accumulate spend from LLM calls anywhere underneath."""

    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        return {"content": "x", "input_tokens": 500, "output_tokens": 250}

    @trace_agent(name="child", budget_usd=10.0)
    def child():
        call("inner")
        return "child-done"

    @trace_agent(name="parent", budget_usd=0.0001)
    def parent():
        child()
        return "parent-done"

    with pytest.raises(BudgetExceeded) as exc_info:
        parent()
    assert exc_info.value.agent_name == "parent"


def test_sibling_agents_do_not_share_budget(temp_storage):
    """Two sequential agents with their own budgets: spend in one doesn't affect the other."""

    @trace_llm_call(model="gpt-4o")
    def call(p: str) -> dict:
        return {"content": "x", "input_tokens": 100, "output_tokens": 50}

    @trace_agent(name="a", budget_usd=10.0)
    def a():
        call("a")
        return "ok"

    @trace_agent(name="b", budget_usd=10.0)
    def b():
        call("b")
        return "ok"

    assert a() == "ok"
    assert b() == "ok"

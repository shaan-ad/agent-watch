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

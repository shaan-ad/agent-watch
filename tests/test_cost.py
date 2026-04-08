"""Tests for cost estimation."""

from __future__ import annotations

import pytest

from agent_watch.cost import estimate_cost, get_pricing, list_models, reset_cache


@pytest.fixture(autouse=True)
def reset_pricing():
    reset_cache()
    yield
    reset_cache()


def test_claude_sonnet_pricing():
    pricing = get_pricing("claude-sonnet-4-20250514")
    assert pricing is not None
    assert pricing["input"] == 3.0
    assert pricing["output"] == 15.0


def test_gpt4o_pricing():
    pricing = get_pricing("gpt-4o")
    assert pricing is not None
    assert pricing["input"] == 2.50
    assert pricing["output"] == 10.0


def test_unknown_model_returns_none():
    assert get_pricing("unknown-model-xyz") is None
    assert estimate_cost("unknown-model-xyz", 100, 50) is None


def test_estimate_cost_claude_sonnet():
    # 1000 input tokens + 500 output tokens at Claude Sonnet pricing
    # Input: 1000/1M * $3.0 = $0.003
    # Output: 500/1M * $15.0 = $0.0075
    # Total: $0.0105
    cost = estimate_cost("claude-sonnet-4-20250514", input_tokens=1000, output_tokens=500)
    assert cost is not None
    assert abs(cost - 0.0105) < 0.0001


def test_estimate_cost_gpt4o():
    # 2000 input + 1000 output at GPT-4o pricing
    # Input: 2000/1M * $2.50 = $0.005
    # Output: 1000/1M * $10.0 = $0.01
    # Total: $0.015
    cost = estimate_cost("gpt-4o", input_tokens=2000, output_tokens=1000)
    assert cost is not None
    assert abs(cost - 0.015) < 0.0001


def test_estimate_cost_zero_tokens():
    cost = estimate_cost("claude-sonnet-4-20250514", input_tokens=0, output_tokens=0)
    assert cost == 0.0


def test_estimate_cost_large_volume():
    # 1M input + 500K output on Claude Opus
    # Input: 1M/1M * $15.0 = $15.0
    # Output: 500K/1M * $75.0 = $37.5
    # Total: $52.5
    cost = estimate_cost("claude-opus-4-20250514", input_tokens=1_000_000, output_tokens=500_000)
    assert cost is not None
    assert abs(cost - 52.5) < 0.01


def test_list_models():
    models = list_models()
    assert "claude-sonnet-4-20250514" in models
    assert "gpt-4o" in models
    assert len(models) >= 10


def test_alias_pricing():
    # Aliases should match full model IDs
    full = get_pricing("claude-sonnet-4-20250514")
    alias = get_pricing("claude-sonnet-4")
    assert full == alias

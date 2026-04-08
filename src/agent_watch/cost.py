"""Cost estimation from token counts using model pricing data."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

import yaml


# Pricing per 1M tokens (input, output) in USD
DEFAULT_PRICING: Dict[str, Dict[str, float]] = {
    # Anthropic
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    # Aliases
    "claude-opus-4": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "claude-haiku-4.5": {"input": 0.80, "output": 4.0},
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "o1": {"input": 15.0, "output": 60.0},
    "o1-mini": {"input": 1.10, "output": 4.40},
    "o3-mini": {"input": 1.10, "output": 4.40},
    # Google
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    # Meta (via API providers, typical pricing)
    "llama-3.1-405b": {"input": 3.0, "output": 3.0},
    "llama-3.1-70b": {"input": 0.80, "output": 0.80},
    "llama-3.1-8b": {"input": 0.10, "output": 0.10},
}

_custom_pricing: Optional[Dict[str, Dict[str, float]]] = None


def _load_custom_pricing() -> Dict[str, Dict[str, float]]:
    """Load custom pricing from YAML file if it exists."""
    global _custom_pricing
    if _custom_pricing is not None:
        return _custom_pricing

    # Check for user override file
    custom_path = os.environ.get("AGENT_WATCH_PRICING")
    if custom_path and Path(custom_path).exists():
        with open(custom_path) as f:
            data = yaml.safe_load(f)
            _custom_pricing = data.get("models", {})
            return _custom_pricing

    # Check for bundled pricing.yaml
    bundled = Path(__file__).parent / "pricing.yaml"
    if bundled.exists():
        with open(bundled) as f:
            data = yaml.safe_load(f)
            _custom_pricing = data.get("models", {})
            return _custom_pricing

    _custom_pricing = {}
    return _custom_pricing


def get_pricing(model: str) -> Optional[Dict[str, float]]:
    """Get pricing for a model. Returns {"input": X, "output": Y} per 1M tokens."""
    custom = _load_custom_pricing()
    if model in custom:
        return custom[model]
    return DEFAULT_PRICING.get(model)


def estimate_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> Optional[float]:
    """Estimate cost in USD for a given model and token counts.

    Returns None if the model is not in the pricing table.
    """
    pricing = get_pricing(model)
    if pricing is None:
        return None

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)


def list_models() -> list:
    """List all models with known pricing."""
    custom = _load_custom_pricing()
    all_models = set(DEFAULT_PRICING.keys()) | set(custom.keys())
    return sorted(all_models)


def reset_cache() -> None:
    """Reset the custom pricing cache (for testing)."""
    global _custom_pricing
    _custom_pricing = None

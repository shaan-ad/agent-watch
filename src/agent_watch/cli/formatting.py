"""Terminal output formatting helpers."""

from __future__ import annotations

from typing import List


def format_cost(cost: float) -> str:
    """Format a cost value as a dollar string."""
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def format_tokens(count: int) -> str:
    """Format a token count with K/M suffixes."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def format_duration(ms: float) -> str:
    """Format a duration in milliseconds."""
    if ms >= 60_000:
        return f"{ms / 60_000:.1f}m"
    if ms >= 1_000:
        return f"{ms / 1_000:.1f}s"
    return f"{ms:.0f}ms"


def format_percentage(value: float) -> str:
    """Format a 0-1 float as a percentage."""
    return f"{value * 100:.1f}%"


def bar_chart(value: float, max_value: float, width: int = 20) -> str:
    """Create a simple bar chart string."""
    if max_value == 0:
        return " " * width
    filled = int((value / max_value) * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def format_table(
    headers: List[str],
    rows: List[List[str]],
    alignments: List[str] | None = None,
) -> str:
    """Format a simple table for terminal output."""
    if not rows:
        return ""

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))

    # Build rows
    lines = []

    # Header
    header_parts = []
    for i, h in enumerate(headers):
        header_parts.append(h.ljust(widths[i]))
    lines.append("  ".join(header_parts))

    # Separator
    lines.append("  ".join("-" * w for w in widths))

    # Data rows
    for row in rows:
        parts = []
        for i, cell in enumerate(row):
            if i < len(widths):
                if alignments and i < len(alignments) and alignments[i] == "right":
                    parts.append(cell.rjust(widths[i]))
                else:
                    parts.append(cell.ljust(widths[i]))
        lines.append("  ".join(parts))

    return "\n".join(lines)

"""Read and query telemetry data from JSONL files."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from agent_watch import otel
from agent_watch.collector import get_storage_dir
from agent_watch.types import Span


def load_spans(
    days: int = 7,
    agent_name: Optional[str] = None,
    status: Optional[str] = None,
    kind: Optional[str] = None,
    storage_dir: Optional[Path] = None,
) -> List[Span]:
    """Load spans from JSONL files, with optional filtering."""
    dir_path = storage_dir or get_storage_dir()
    if not dir_path.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    spans: List[Span] = []

    for filepath in sorted(dir_path.glob("*.jsonl")):
        try:
            file_date = datetime.strptime(filepath.stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if file_date < cutoff - timedelta(days=1):
                continue
        except ValueError:
            continue

        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    span = Span.from_json(line)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue

                if agent_name and span.name != agent_name:
                    continue
                if status and span.status != status:
                    continue
                if kind and span.kind != kind:
                    continue
                if span.start_time < cutoff.timestamp():
                    continue

                spans.append(span)

    return spans


# Back-compat alias for code that still calls load_events with old arg names
def load_events(
    days: int = 7,
    agent_name: Optional[str] = None,
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    storage_dir: Optional[Path] = None,
) -> List[Span]:
    """Deprecated: use load_spans. Translates v0.1 argument names."""
    kind_map = {"agent_run": otel.KIND_AGENT, "llm_call": otel.KIND_LLM, "span": otel.KIND_SPAN}
    kind = kind_map.get(event_type) if event_type else None
    status_map = {"success": otel.STATUS_OK, "error": otel.STATUS_ERROR}
    mapped_status = status_map.get(status, status) if status else None
    return load_spans(
        days=days, agent_name=agent_name, status=mapped_status, kind=kind, storage_dir=storage_dir
    )


def aggregate_by_agent(spans: List[Span]) -> Dict[str, AgentStats]:
    """Aggregate spans by agent name (kind=agent only)."""
    stats: Dict[str, AgentStats] = {}
    for span in spans:
        if span.kind != otel.KIND_AGENT:
            continue
        if span.name not in stats:
            stats[span.name] = AgentStats(name=span.name)
        stats[span.name].add(span)
    return stats


def aggregate_by_model(spans: List[Span]) -> Dict[str, ModelStats]:
    """Aggregate LLM call spans by model."""
    stats: Dict[str, ModelStats] = {}
    for span in spans:
        if span.kind != otel.KIND_LLM:
            continue
        model = span.attributes.get(otel.GEN_AI_REQUEST_MODEL, "unknown")
        if model not in stats:
            stats[model] = ModelStats(model=model)
        stats[model].add(span)
    return stats


class AgentStats:
    """Aggregated statistics for a single agent."""

    def __init__(self, name: str):
        self.name = name
        self.total_runs = 0
        self.successes = 0
        self.failures = 0
        self.total_duration_ms = 0.0
        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.error_messages: list[str] = []

    def add(self, span: Span) -> None:
        self.total_runs += 1
        if span.status == otel.STATUS_OK:
            self.successes += 1
        else:
            self.failures += 1
            if span.error:
                self.error_messages.append(span.error)
        self.total_duration_ms += span.duration_ms
        self.total_cost += span.attributes.get(otel.AGENT_WATCH_COST_USD, 0.0)
        self.total_input_tokens += span.attributes.get(otel.GEN_AI_USAGE_INPUT_TOKENS, 0)
        self.total_output_tokens += span.attributes.get(otel.GEN_AI_USAGE_OUTPUT_TOKENS, 0)

    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.successes / self.total_runs

    @property
    def avg_duration_ms(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.total_duration_ms / self.total_runs


class ModelStats:
    """Aggregated statistics for a single model."""

    def __init__(self, model: str):
        self.model = model
        self.total_calls = 0
        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_duration_ms = 0.0

    def add(self, span: Span) -> None:
        self.total_calls += 1
        self.total_cost += span.attributes.get(otel.AGENT_WATCH_COST_USD, 0.0)
        self.total_input_tokens += span.attributes.get(otel.GEN_AI_USAGE_INPUT_TOKENS, 0)
        self.total_output_tokens += span.attributes.get(otel.GEN_AI_USAGE_OUTPUT_TOKENS, 0)
        self.total_duration_ms += span.duration_ms

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def avg_duration_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_duration_ms / self.total_calls

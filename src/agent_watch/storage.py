"""Read and query telemetry data from JSONL files."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from agent_watch.collector import get_storage_dir
from agent_watch.types import Event


def load_events(
    days: int = 7,
    agent_name: Optional[str] = None,
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    storage_dir: Optional[Path] = None,
) -> List[Event]:
    """Load events from JSONL files, with optional filtering.

    Args:
        days: Number of days to look back.
        agent_name: Filter by agent/span name.
        status: Filter by status ("success" or "error").
        event_type: Filter by event type ("agent_run", "llm_call", "span").
        storage_dir: Override storage directory (for testing).
    """
    dir_path = storage_dir or get_storage_dir()
    if not dir_path.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events: List[Event] = []

    for filepath in sorted(dir_path.glob("*.jsonl")):
        # Quick date filter from filename (YYYY-MM-DD.jsonl)
        try:
            file_date = datetime.strptime(filepath.stem, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
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
                    event = Event.from_json(line)
                except (json.JSONDecodeError, TypeError):
                    continue

                # Apply filters
                if agent_name and event.name != agent_name:
                    continue
                if status and event.status != status:
                    continue
                if event_type and event.type != event_type:
                    continue
                if event.start_time < cutoff.timestamp():
                    continue

                events.append(event)

    return events


def aggregate_by_agent(events: List[Event]) -> Dict[str, AgentStats]:
    """Aggregate events by agent name."""
    stats: Dict[str, AgentStats] = {}
    for event in events:
        if event.type != "agent_run":
            continue
        if event.name not in stats:
            stats[event.name] = AgentStats(name=event.name)
        stats[event.name].add(event)
    return stats


def aggregate_by_model(events: List[Event]) -> Dict[str, ModelStats]:
    """Aggregate LLM call events by model."""
    stats: Dict[str, ModelStats] = {}
    for event in events:
        if event.type != "llm_call":
            continue
        model = event.metadata.get("model", "unknown")
        if model not in stats:
            stats[model] = ModelStats(model=model)
        stats[model].add(event)
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

    def add(self, event: Event) -> None:
        self.total_runs += 1
        if event.status == "success":
            self.successes += 1
        else:
            self.failures += 1
            if event.error:
                self.error_messages.append(event.error)
        self.total_duration_ms += event.duration_ms
        self.total_cost += event.metadata.get("cost_usd", 0.0)
        self.total_input_tokens += event.metadata.get("input_tokens", 0)
        self.total_output_tokens += event.metadata.get("output_tokens", 0)

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

    def add(self, event: Event) -> None:
        self.total_calls += 1
        self.total_cost += event.metadata.get("cost_usd", 0.0)
        self.total_input_tokens += event.metadata.get("input_tokens", 0)
        self.total_output_tokens += event.metadata.get("output_tokens", 0)
        self.total_duration_ms += event.duration_ms

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def avg_duration_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_duration_ms / self.total_calls

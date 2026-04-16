"""Tests for OTel attribute constants and schema mapping."""

from agent_watch import otel
from agent_watch.types import Span, make_agent_span, make_llm_span, make_generic_span


def test_gen_ai_attribute_constants_exist():
    assert otel.GEN_AI_REQUEST_MODEL == "gen_ai.request.model"
    assert otel.GEN_AI_USAGE_INPUT_TOKENS == "gen_ai.usage.input_tokens"
    assert otel.GEN_AI_USAGE_OUTPUT_TOKENS == "gen_ai.usage.output_tokens"
    assert otel.GEN_AI_SYSTEM == "gen_ai.system"
    assert otel.GEN_AI_OPERATION_NAME == "gen_ai.operation.name"


def test_agent_watch_namespaced_constants_exist():
    assert otel.AGENT_WATCH_COST_USD == "agent_watch.cost_usd"
    assert otel.AGENT_WATCH_TAGS == "agent_watch.tags"


def test_schema_version_constant():
    assert otel.SCHEMA_VERSION == "agent-watch/v1"


def test_span_kind_constants():
    assert otel.KIND_AGENT == "agent"
    assert otel.KIND_LLM == "llm"
    assert otel.KIND_SPAN == "span"


def test_status_constants():
    assert otel.STATUS_OK == "ok"
    assert otel.STATUS_ERROR == "error"


def test_span_has_v1_fields():
    s = Span(name="test")
    assert hasattr(s, "span_id")
    assert hasattr(s, "trace_id")
    assert hasattr(s, "parent_span_id")
    assert hasattr(s, "kind")
    assert hasattr(s, "attributes")
    assert hasattr(s, "schema")
    assert s.schema == otel.SCHEMA_VERSION


def test_span_defaults():
    s = Span(name="x")
    assert s.span_id  # non-empty UUID
    assert s.trace_id  # non-empty UUID
    assert s.parent_span_id is None
    assert s.kind == otel.KIND_SPAN
    assert s.status == otel.STATUS_OK
    assert s.attributes == {}
    assert s.schema == otel.SCHEMA_VERSION


def test_span_serialization_roundtrip():
    s = Span(name="agent-x", kind=otel.KIND_AGENT)
    s.attributes[otel.GEN_AI_REQUEST_MODEL] = "gpt-4o"
    s.attributes[otel.AGENT_WATCH_COST_USD] = 0.123
    line = s.to_json()
    parsed = Span.from_json(line)
    assert parsed.span_id == s.span_id
    assert parsed.trace_id == s.trace_id
    assert parsed.kind == otel.KIND_AGENT
    assert parsed.attributes[otel.GEN_AI_REQUEST_MODEL] == "gpt-4o"
    assert parsed.attributes[otel.AGENT_WATCH_COST_USD] == 0.123
    assert parsed.schema == otel.SCHEMA_VERSION


def test_span_from_json_reads_v01_legacy_format():
    # An old v0.1 JSONL line uses 'id', 'type', 'parent_id', 'metadata'
    legacy = (
        '{"id": "old-1", "type": "agent_run", "name": "legacy-agent", '
        '"parent_id": null, "start_time": 100.0, "end_time": 101.0, '
        '"duration_ms": 1000.0, "status": "success", "error": null, '
        '"input_preview": "q", "output_preview": "a", '
        '"metadata": {"model": "gpt-4", "cost_usd": 0.5, "tags": ["x"]}, '
        '"children": []}'
    )
    s = Span.from_json(legacy)
    assert s.span_id == "old-1"
    assert s.kind == otel.KIND_AGENT  # agent_run -> agent
    assert s.parent_span_id is None
    assert s.status == otel.STATUS_OK  # success -> ok
    assert s.attributes[otel.GEN_AI_REQUEST_MODEL] == "gpt-4"
    assert s.attributes[otel.AGENT_WATCH_COST_USD] == 0.5
    assert s.attributes[otel.AGENT_WATCH_TAGS] == ["x"]
    # Legacy spans get a synthetic trace_id equal to their span_id
    assert s.trace_id == "old-1"


def test_make_agent_span_sets_kind():
    s = make_agent_span("research", tags=["prod"])
    assert s.kind == otel.KIND_AGENT
    assert s.name == "research"
    assert s.attributes[otel.AGENT_WATCH_TAGS] == ["prod"]


def test_make_llm_span_sets_kind_and_model():
    s = make_llm_span("call_claude", model="claude-sonnet-4-20250514")
    assert s.kind == otel.KIND_LLM
    assert s.name == "call_claude"
    assert s.attributes[otel.GEN_AI_REQUEST_MODEL] == "claude-sonnet-4-20250514"


def test_make_generic_span_sets_kind():
    s = make_generic_span("preprocessing")
    assert s.kind == otel.KIND_SPAN

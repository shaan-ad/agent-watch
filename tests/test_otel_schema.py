"""Tests for OTel attribute constants and schema mapping."""

from agent_watch import otel


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

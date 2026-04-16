"""OpenTelemetry GenAI semantic convention constants and Agent Watch namespaced keys.

This module is the single source of truth for attribute key names. Decorators,
collectors, readers, and exporters all reference these constants.

References:
- OTel GenAI conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
"""

# --- OTel GenAI standard attribute keys ---
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_AGENT_ID = "gen_ai.agent.id"

# --- Agent Watch namespaced keys (not in OTel spec) ---
AGENT_WATCH_COST_USD = "agent_watch.cost_usd"
AGENT_WATCH_TAGS = "agent_watch.tags"
AGENT_WATCH_BUDGET_USD = "agent_watch.budget_usd"
AGENT_WATCH_BUDGET_EXCEEDED = "agent_watch.budget_exceeded"

# --- Schema version ---
SCHEMA_VERSION = "agent-watch/v1"

# --- Span kinds (Agent Watch-specific taxonomy) ---
KIND_AGENT = "agent"
KIND_LLM = "llm"
KIND_SPAN = "span"

# --- Status values (aligned with OTel StatusCode lowercased) ---
STATUS_OK = "ok"
STATUS_ERROR = "error"

"""DTOs for operational Telemetry MCP tools."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ...runtime.policy_config import compose_retention_days
from .base import DTO, JsonObject


class FlushInput(DTO):
    timeout_ms: int = 5000


class FlushOutput(DTO):
    ok: bool
    flushed: list[str] = []
    error: str | None = None


class RetentionInput(DTO):
    raw_days: int = Field(default_factory=lambda: compose_retention_days()[0])
    rollup_days: int = Field(default_factory=lambda: compose_retention_days()[1])
    compact_source: bool = True


class RetentionOutput(DTO):
    rolled_up_days: int
    source_rows_deleted: int
    raw_rows_pruned: int
    rollups_pruned: int
    source_bytes_after: int


class RecordLogInput(DTO):
    severity: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR"]
    body: str
    attributes: JsonObject | None = None
    trace_id: str | None = None
    span_id: str | None = None


class LlmInteractionInput(DTO):
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float | None = None
    cost_usd: float | None = None
    agent_id: str | None = None
    workflow_id: str | None = None
    trace_attributes: JsonObject | None = None


class AgentExecutionInput(DTO):
    agent_id: str
    workflow_id: str
    success: bool = True
    latency_ms: float | None = None
    trace_attributes: JsonObject | None = None


class ToolInvocationInput(DTO):
    tool_name: str
    workflow_id: str | None = None
    success: bool = True
    latency_ms: float | None = None
    trace_attributes: JsonObject | None = None


class RecordedOutput(DTO):
    ok: bool
    recorded: Literal["log", "llm_interaction", "agent_execution", "tool_invocation"]


class StartSpanInput(DTO):
    name: str
    attributes: JsonObject | None = None


class SpanOutput(DTO):
    ok: bool
    span_id: str | None = None
    error: str | None = None


class EndSpanInput(DTO):
    span_id: str
    error: str | None = None

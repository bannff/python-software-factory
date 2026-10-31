"""Strict typed deterministic MCP tools for the Logger brick."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field
from factory.mcp_utils.interface import ToolResult, deterministic, ok
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    CapabilitiesOutput,
    ConfigSchemaOutput,
    EmptyInput,
    HealthOutput,
    LogLevelValue,
    RecordsOutput,
    SearchInput,
    TailInput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import LoggerRuntime


_SAFE_FAILURE = "logger_operation_failed"
_REDACTED = "[redacted]"
_PATH_PATTERN = re.compile(r"(?:~|/)[^\s]+")
_SENSITIVE_KEY_TOKENS = ("error", "exception", "traceback", "stack_trace")


def _redact_value(value: Any, *, key: str | None = None) -> Any:
    """Remove paths and exception detail from persisted log data at MCP egress."""
    if key and any(token in key.lower() for token in _SENSITIVE_KEY_TOKENS):
        return _REDACTED
    if isinstance(value, str):
        if "traceback" in value.lower():
            return _REDACTED
        return _PATH_PATTERN.sub(_REDACTED, value)
    if isinstance(value, dict):
        return {str(item_key): _redact_value(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _records_output(records: list[dict[str, Any]]) -> RecordsOutput:
    """Project runtime records through the safe MCP redaction boundary."""
    projected = [
        {
            **record,
            "message": _redact_value(record["message"]),
            "source": _redact_value(record.get("source")),
            "run_id": _redact_value(record.get("run_id")),
            "context": _redact_value(record.get("context", {})),
        }
        for record in records
    ]
    return RecordsOutput(records=projected, count=len(projected))


def _safe_health(result: dict[str, Any]) -> HealthOutput:
    """Normalize any supported sink health response without adapter-specific paths."""
    sink = result["sink"]
    return HealthOutput(
        status=result["status"],
        sink={
            "backend": str(sink.get("backend", sink.get("sink", "unknown"))),
            "writable": bool(sink.get("writable", False)),
            "log_size": sink.get("log_size"),
            "exists": sink.get("exists"),
        },
    )


def register(mcp: Any, runtime: "LoggerRuntime") -> None:
    """Register deterministic tools with strict flat ingress and typed egress."""

    @typed_tool(mcp, name="logger.get_capabilities")
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Get logger capabilities."""
        try:
            return ok(CapabilitiesOutput(document=runtime.get_capabilities()))
        except Exception:
            return ToolResult(ok=False, error=_SAFE_FAILURE)

    @typed_tool(mcp, name="logger.health_check")
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        """Check logger health status without exposing filesystem paths."""
        try:
            return ok(_safe_health(runtime.health_check()))
        except Exception:
            return ToolResult(ok=False, error=_SAFE_FAILURE)

    @typed_tool(mcp, name="logger.describe_config_schema")
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Get configuration schema."""
        try:
            return ok(ConfigSchemaOutput(document=runtime.describe_config_schema()))
        except Exception:
            return ToolResult(ok=False, error=_SAFE_FAILURE)

    @typed_tool(mcp, name="logger.tail")
    @deterministic(input_model=TailInput, output_model=RecordsOutput)
    def tail(
        lines: Annotated[int, Field(default=20, ge=1, le=1_000)] = 20,
    ) -> ToolResult[RecordsOutput]:
        """Get the last N log entries."""
        try:
            return ok(_records_output(runtime.tail(n=lines)))
        except Exception:
            return ToolResult(ok=False, error=_SAFE_FAILURE)

    @typed_tool(mcp, name="logger.search")
    @deterministic(input_model=SearchInput, output_model=RecordsOutput)
    def search(
        level: LogLevelValue | None = None,
        source: Annotated[str | None, Field(default=None, max_length=256)] = None,
        run_id: Annotated[str | None, Field(default=None, max_length=256)] = None,
        limit: Annotated[int, Field(default=100, ge=1, le=1_000)] = 100,
    ) -> ToolResult[RecordsOutput]:
        """Search logs with filters."""
        try:
            return ok(_records_output(runtime.search(
                level=level, source=source, run_id=run_id, limit=limit,
            )))
        except Exception:
            return ToolResult(ok=False, error=_SAFE_FAILURE)

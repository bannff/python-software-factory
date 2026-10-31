"""Strict typed operational MCP tools for the Logger brick."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, ok, operational
from factory.mcp_utils.registration import typed_tool

from .contracts import JsonObject, LogInput, LogOutput
from pydantic import Field
from typing import Annotated

if TYPE_CHECKING:
    from ..runtime.runtime import LoggerRuntime


_SAFE_FAILURE = "logger_operation_failed"


def _log(
    runtime: "LoggerRuntime", level: str, message: str, source: str | None,
    run_id: str | None, context: dict | None,
) -> ToolResult[LogOutput]:
    """Write a log record and project only the safe runtime result fields."""
    try:
        result = getattr(runtime, level)(
            message, source=source, run_id=run_id, context=context,
        )
        return ok(LogOutput(**result))
    except Exception:
        return ToolResult(ok=False, error=_SAFE_FAILURE)


def register(mcp: Any, runtime: "LoggerRuntime") -> None:
    """Register operational tools with strict flat ingress and typed egress."""

    @typed_tool(mcp, name="logger.info")
    @operational(input_model=LogInput, output_model=LogOutput)
    def log_info(
        message: Annotated[str, Field(min_length=1, max_length=65_536)],
        source: Annotated[str | None, Field(default=None, max_length=256)] = None,
        run_id: Annotated[str | None, Field(default=None, max_length=256)] = None,
        context: JsonObject | None = None,
    ) -> ToolResult[LogOutput]:
        """Log an INFO level message."""
        return _log(runtime, "info", message, source, run_id, context)

    @typed_tool(mcp, name="logger.error")
    @operational(input_model=LogInput, output_model=LogOutput)
    def log_error(
        message: Annotated[str, Field(min_length=1, max_length=65_536)],
        source: Annotated[str | None, Field(default=None, max_length=256)] = None,
        run_id: Annotated[str | None, Field(default=None, max_length=256)] = None,
        context: JsonObject | None = None,
    ) -> ToolResult[LogOutput]:
        """Log an ERROR level message."""
        return _log(runtime, "error", message, source, run_id, context)

    @typed_tool(mcp, name="logger.warning")
    @operational(input_model=LogInput, output_model=LogOutput)
    def log_warning(
        message: Annotated[str, Field(min_length=1, max_length=65_536)],
        source: Annotated[str | None, Field(default=None, max_length=256)] = None,
        run_id: Annotated[str | None, Field(default=None, max_length=256)] = None,
        context: JsonObject | None = None,
    ) -> ToolResult[LogOutput]:
        """Log a WARNING level message."""
        return _log(runtime, "warning", message, source, run_id, context)

    @typed_tool(mcp, name="logger.debug")
    @operational(input_model=LogInput, output_model=LogOutput)
    def log_debug(
        message: Annotated[str, Field(min_length=1, max_length=65_536)],
        source: Annotated[str | None, Field(default=None, max_length=256)] = None,
        run_id: Annotated[str | None, Field(default=None, max_length=256)] = None,
        context: JsonObject | None = None,
    ) -> ToolResult[LogOutput]:
        """Log a DEBUG level message."""
        return _log(runtime, "debug", message, source, run_id, context)

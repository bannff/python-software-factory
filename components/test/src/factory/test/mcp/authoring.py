"""Authoring MCP tools for the Test runtime's in-memory configuration."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.decorators import authoring
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

from .contracts import AdapterInput, AuthoringStatusOutput, EmptyInput, MutationOutput, PatternInput, TimeoutInput, VerboseInput
from ..runtime.mcp_containment import is_valid_pattern

if TYPE_CHECKING:
    from pathlib import Path
    from ..runtime.runtime import TestRuntime

_CAPABILITIES = ["set_default_adapter", "set_default_pattern", "set_timeout", "set_verbose"]


def _valid_pattern(pattern: str) -> bool:
    return is_valid_pattern(pattern)


def register(mcp: Any, get_runtime: Callable[[], "TestRuntime"],
             get_config_dir: Callable[[], "Path"]) -> None:
    """Register truthful, runtime-held Test configuration changes."""

    @typed_tool(mcp)
    @authoring(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def test_authoring_get_status() -> ToolResult[AuthoringStatusOutput]:
        """Return the authoring gate and current runtime defaults."""
        runtime = get_runtime()
        return ok(AuthoringStatusOutput(
            enabled=runtime.authoring_enabled, config_dir="<configured>",
            config_dir_exists=get_config_dir().exists(),
            capabilities=_CAPABILITIES if runtime.authoring_enabled else [],
            adapter=runtime.adapter_type, pattern=runtime.default_pattern,
            timeout_seconds=runtime.timeout_seconds, verbose=runtime.default_verbose,
        ))

    @typed_tool(mcp)
    @authoring(input_model=AdapterInput, output_model=MutationOutput)
    def test_authoring_set_adapter(adapter: str) -> ToolResult[MutationOutput]:
        """Set the runtime's default adapter for later MCP execution."""
        runtime = get_runtime()
        if not runtime.authoring_enabled:
            return ok(MutationOutput(success=False, error="authoring_disabled"))
        if adapter not in ("pytest", "memory"):
            return ok(MutationOutput(success=False, error="invalid_adapter"))
        runtime.set_default_adapter(adapter)  # type: ignore[arg-type]
        return ok(MutationOutput(success=True, adapter=adapter, message="default_adapter_updated"))

    @typed_tool(mcp)
    @authoring(input_model=TimeoutInput, output_model=MutationOutput)
    def test_authoring_set_timeout(timeout_seconds: int) -> ToolResult[MutationOutput]:
        """Set the bounded default test execution timeout."""
        runtime = get_runtime()
        if not runtime.authoring_enabled:
            return ok(MutationOutput(success=False, error="authoring_disabled"))
        if not 0 < timeout_seconds <= 3600:
            return ok(MutationOutput(success=False, error="invalid_timeout"))
        runtime.set_default_timeout(timeout_seconds)
        return ok(MutationOutput(success=True, timeout_seconds=timeout_seconds,
                                  message="default_timeout_updated"))

    @typed_tool(mcp)
    @authoring(input_model=PatternInput, output_model=MutationOutput)
    def test_authoring_set_pattern(pattern: str) -> ToolResult[MutationOutput]:
        """Set the contained default test-file pattern."""
        runtime = get_runtime()
        if not runtime.authoring_enabled:
            return ok(MutationOutput(success=False, error="authoring_disabled"))
        if not _valid_pattern(pattern):
            return ok(MutationOutput(success=False, error="invalid_pattern"))
        runtime.set_default_pattern(pattern)
        return ok(MutationOutput(success=True, pattern=pattern, message="default_pattern_updated"))

    @typed_tool(mcp)
    @authoring(input_model=VerboseInput, output_model=MutationOutput)
    def test_authoring_set_verbose(verbose: bool) -> ToolResult[MutationOutput]:
        """Set the default verbose output mode."""
        runtime = get_runtime()
        if not runtime.authoring_enabled:
            return ok(MutationOutput(success=False, error="authoring_disabled"))
        runtime.set_default_verbose(verbose)
        return ok(MutationOutput(success=True, verbose=verbose, message="default_verbose_updated"))

"""Operational MCP tools for bounded Test execution."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.decorators import operational
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

from .contracts import (
    ComponentRunInput, EmptyInput, ExecutionOutput, ListFilesOutput, PathRunInput,
    RunAllInput, supplied_input_fields,
)
from ..runtime.mcp_containment import ContainmentError, McpTestRuntime

if TYPE_CHECKING:
    from ..runtime.runtime import TestRuntime


def register(mcp: Any, get_runtime: Callable[[], "TestRuntime"]) -> None:
    """Register stateful Test tools; all process entry is containment checked."""

    @typed_tool(mcp)
    @operational(input_model=RunAllInput, output_model=ExecutionOutput)
    def test_run_all(verbose: bool = False) -> ToolResult[ExecutionOutput]:
        """Run all workspace tests through the trusted-local adapter."""
        facade = McpTestRuntime(get_runtime())
        return ok(ExecutionOutput(**facade.run_all(
            verbose, verbose_supplied="verbose" in supplied_input_fields()
        )))

    @typed_tool(mcp)
    @operational(input_model=ComponentRunInput, output_model=ExecutionOutput)
    def test_run_component(component_name: str, verbose: bool = False) -> ToolResult[ExecutionOutput]:
        """Run tests for one allowlisted component name."""
        facade = McpTestRuntime(get_runtime())
        try:
            return ok(ExecutionOutput(**facade.run_component(
                component_name, verbose,
                verbose_supplied="verbose" in supplied_input_fields(),
            )))
        except ContainmentError as exc:
            return ok(ExecutionOutput(**facade.rejected_execution(exc.code)))

    @typed_tool(mcp)
    @operational(input_model=PathRunInput, output_model=ExecutionOutput)
    def test_run_path(path: str, pattern: str = "test_*.py", verbose: bool = False) -> ToolResult[ExecutionOutput]:
        """Run tests at a contained workspace-relative path."""
        facade = McpTestRuntime(get_runtime())
        try:
            fields = supplied_input_fields()
            return ok(ExecutionOutput(**facade.run_path(
                path, pattern, verbose,
                pattern_supplied="pattern" in fields,
                verbose_supplied="verbose" in fields,
            )))
        except ContainmentError as exc:
            return ok(ExecutionOutput(**facade.rejected_execution(exc.code)))

    @typed_tool(mcp)
    @operational(input_model=EmptyInput, output_model=ListFilesOutput)
    def test_list_files() -> ToolResult[ListFilesOutput]:
        """List contained test files discovered in the workspace."""
        return ok(ListFilesOutput(**McpTestRuntime(get_runtime()).list_files()))

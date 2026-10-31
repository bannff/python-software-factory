"""MCP Prompt registration for Test brick.

Prompts provide guided workflows for common tasks:
- Running tests
- Debugging test failures
- Adding tests to components
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any

from .templates import PROMPT_TEMPLATES

if TYPE_CHECKING:
    from pathlib import Path
    from ..runtime.runtime import TestRuntime


def register(
    mcp: Any,
    get_runtime: Callable[[], "TestRuntime"],
    get_config_dir: Callable[[], "Path"],
) -> None:
    """Register all Test prompts with the MCP server."""

    @mcp.prompt()
    def run_tests(
        scope: str = "all",
        component: str = "",
        path: str = ".",
    ) -> str:
        """Generate guidance for running tests.

        Args:
            scope: Test scope - "all", "component", or "path"
            component: Component name (if scope is "component")
            path: Test path (if scope is "path")
        """
        if scope == "component" and component:
            purpose = f"Run tests for the {component} component"
            test_path = f"components/{component}/test"
            run_command = f'test_run_component(component_name="{component}")'
        elif scope == "path" and path != ".":
            purpose = f"Run tests at {path}"
            test_path = path
            run_command = f'test_run_path(path="{path}")'
        else:
            purpose = "Run all tests in the workspace"
            test_path = "."
            run_command = "test_run_all()"

        return PROMPT_TEMPLATES["run_tests"]["template"].format(
            scope=scope,
            purpose=purpose,
            path=test_path,
            run_command=run_command,
        )

    @mcp.prompt()
    def debug_failure(
        test_file: str = "",
        test_name: str = "",
        error_type: str = "AssertionError",
    ) -> str:
        """Generate guidance for debugging test failures.

        Args:
            test_file: Path to the failing test file
            test_name: Name of the failing test
            error_type: Type of error encountered
        """
        error_analyses = {
            "AssertionError": "The assertion failed. Check expected vs actual values.",
            "ImportError": "A module could not be imported. Check dependencies.",
            "AttributeError": "An attribute was not found. Check API changes.",
            "TimeoutError": "The test timed out. Consider mocking slow operations.",
            "TypeError": "Wrong argument types. Check function signatures.",
        }

        error_analysis = error_analyses.get(
            error_type,
            "Review the error message and stack trace for details.",
        )

        return PROMPT_TEMPLATES["debug_failure"]["template"].format(
            test_file=test_file or "unknown",
            test_name=test_name or "unknown",
            error_type=error_type,
            error_analysis=error_analysis,
        )

    @mcp.prompt()
    def add_tests(component: str) -> str:
        """Generate guidance for adding tests to a component.

        Args:
            component: Name of the component to add tests for
        """
        # Convert to PascalCase for class name
        component_class = "".join(
            word.capitalize() for word in component.replace("-", "_").split("_")
        )

        return PROMPT_TEMPLATES["add_tests"]["template"].format(
            component=component,
            ComponentClass=component_class,
        )

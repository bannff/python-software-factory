"""
Tool Registry - Loads and manages custom tools.

Tools are deterministic functions that can be called by agents.
"""

from pathlib import Path
from typing import Any, Callable
import importlib.util
import inspect
import logging


# Global registry for @tool decorated functions
_tool_registry: dict[str, Callable[..., Any]] = {}

logger = logging.getLogger(__name__)


def tool(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to register a function as a tool.

    Usage:
        @tool
        def my_tool(arg1: str, arg2: int) -> dict:
            '''Tool description.'''
            return {"result": arg1 * arg2}
    """
    _tool_registry[func.__name__] = func
    return func


class ToolRegistry:
    """
    Registry for custom tools.

    Loads @tool decorated functions from Python files in a directory.
    """

    def __init__(self, config_dir: Path | str):
        """
        Initialize tool registry.

        Args:
            config_dir: Path to directory containing tool modules
        """
        self.config_dir = Path(config_dir)
        self.tools: dict[str, Callable[..., Any]] = {}

    async def load(self) -> None:
        """Load all tools from directory."""
        if not self.config_dir.exists():
            return

        # Clear global registry before loading
        _tool_registry.clear()

        # Load Python files
        for py_file in self.config_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                # Load module dynamically
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
            except Exception as e:
                logger.warning("Failed to load %s: %s", py_file, e)

        # Copy tools from global registry
        self.tools.update(_tool_registry)

    def register(self, name: str, func: Callable[..., Any]) -> None:
        """Register a tool programmatically."""
        self.tools[name] = func

    def get(self, name: str) -> Callable[..., Any] | None:
        """Get a tool by name."""
        return self.tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools."""
        result = []
        for name, func in self.tools.items():
            # Get function signature
            sig = inspect.signature(func)
            params = [
                {
                    "name": p.name,
                    "type": str(p.annotation) if p.annotation != inspect.Parameter.empty else "Any",
                    "default": str(p.default) if p.default != inspect.Parameter.empty else None,
                }
                for p in sig.parameters.values()
            ]

            result.append(
                {
                    "name": name,
                    "description": func.__doc__ or "",
                    "parameters": params,
                }
            )

        return result

    def call(self, name: str, **kwargs: Any) -> Any:
        """Call a tool by name."""
        func = self.get(name)
        if not func:
            raise ValueError(f"Tool '{name}' not found")
        return func(**kwargs)

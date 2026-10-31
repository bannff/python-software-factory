"""Public interface for API base."""

from __future__ import annotations

from typing import Any

from .runtime.runtime import APIRuntime, get_runtime, reset_runtime

__all__ = ["create_app", "APIRuntime", "get_runtime", "reset_runtime"]


def create_app(adapter_type: str = "rest") -> Any:
    """Create an API application with the specified adapter.

    Args:
        adapter_type: "rest" for FastAPI, "graphql" for GraphQL

    Returns:
        The underlying application instance
    """
    runtime = get_runtime(adapter_type)
    return runtime.get_app()

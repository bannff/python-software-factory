"""Polylith Interface for permissions module."""

from .server import create_mcp_server  # noqa: F401
from .runtime.runtime import PermissionsRuntime  # noqa: F401
from .access import DecisionPointPort, create_decision_point

Runtime = PermissionsRuntime

__all__ = [
    "DecisionPointPort", "PermissionsRuntime", "Runtime",
    "create_decision_point", "create_mcp_server",
]

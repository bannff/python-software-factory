"""Process-level service registry for cross-brick callbacks.

Allows bases to register callbacks that components can use without
importing each other. Both sides depend only on mcp_utils.

Usage (base layer — registers):
    from factory.mcp_utils.registry import set_service
    set_service("tool_invoker", aggregator.invoke_tool)

Usage (component layer — consumes):
    from factory.mcp_utils.registry import get_service
    invoker = get_service("tool_invoker")
"""

from typing import Any

_services: dict[str, Any] = {}


def set_service(name: str, value: Any) -> None:
    """Register a service callback by name."""
    _services[name] = value


def get_service(name: str) -> Any | None:
    """Retrieve a registered service callback, or None."""
    return _services.get(name)

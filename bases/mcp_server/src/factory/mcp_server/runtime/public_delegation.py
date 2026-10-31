"""Public-only brick tool delegation."""
from __future__ import annotations

from typing import Any

from .public_admission import project_public_tools
from .tool_dispatch import invoke_catalog_tool, resolve_tool_name, transport_failure


def _not_found() -> dict[str, Any]:
    return transport_failure("ToolNotFoundError", "tool_not_found")


async def call_public_brick_tool(
    aggregator: Any,
    brick_name: str,
    tool_name: str,
    arguments: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve flat calls through the same public projection as discovery."""
    if aggregator._lazy is not None:
        return await aggregator._lazy.call_public_brick_tool(
            brick_name, tool_name, arguments,
        )
    catalog = aggregator._flat_bricks.get(brick_name)
    if catalog is None:
        return _not_found()
    projection = project_public_tools(((brick_name, catalog.tool_map()),))
    admitted = {item.source_name: item for item in projection.admitted}
    resolved = resolve_tool_name(
        {name: item.tool for name, item in admitted.items()}, brick_name, tool_name,
    )
    if resolved is None:
        return _not_found()
    from .authorization import is_authorized, trusted_arguments
    item = admitted[resolved]
    trusted = trusted_arguments(item.tool, arguments)
    if trusted is None or not is_authorized(item, "execute"):
        return transport_failure("AuthorizationError", "authorization_denied")
    return await invoke_catalog_tool(
        item.tool, brick_name, resolved, trusted,
    )


__all__ = ["call_public_brick_tool"]

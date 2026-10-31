"""Authorization helpers for the native MCP callback composer."""
from __future__ import annotations

import json
from typing import Any

from .access_control import AccessOperation
from .tool_result import fail


def operation(item: Any, action: str) -> AccessOperation:
    category = getattr(item.handler, "_mcp_category", None)
    return AccessOperation(
        action=action, public_name=item.name,
        brick=item.brick_name or "mcp_server",
        source_name=item.source_name or item.name,
        category=str(category) if category is not None else None,
    )


def authorization_failure(text_content: type[Any]) -> Any:
    """Return a stable denial without policy, token, or principal details."""
    from mcp.types import CallToolResult

    envelope = fail("authorization_denied").model_dump(mode="json")
    return CallToolResult(
        content=[text_content(
            type="text", text=json.dumps(envelope, separators=(",", ":")),
        )],
        structured_content=envelope, is_error=True,
    )


__all__ = ["authorization_failure", "operation"]

"""Direct Graph tool invocation isolated from parent task idempotency."""
from __future__ import annotations

import asyncio
from typing import Any


def call_graph(runtime: dict[str, Any] | None, tool_name: str, **kwargs: Any) -> Any:
    """Call one sink writer without replaying the parent Workflow attempt."""
    if not runtime or (tool := runtime.get(tool_name)) is None:
        return None

    from factory.mcp_utils.interface import (
        get_envelope, reset_envelope, set_envelope,
    )

    envelope = dict(get_envelope() or {})
    attributes = dict(envelope.get("attributes") or {})
    cleaned = {
        key: value for key, value in attributes.items()
        if key not in {"workflow_attempt_id", "idempotency_key"}
    }
    token = None
    if cleaned != attributes:
        envelope["attributes"] = cleaned
        token = set_envelope(envelope)
    try:
        result = tool.fn(**kwargs)
        return asyncio.run(result) if hasattr(result, "__await__") else result
    finally:
        reset_envelope(token)

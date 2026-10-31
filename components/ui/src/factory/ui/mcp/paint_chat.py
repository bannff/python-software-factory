"""Free-form A2UI paint into chat (carrier #1 producer)."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, fail, operational

from .paint_canvas import _error_for_payload
from .paint_canvas_lift import lift_props_children
from .paint_dtos import ChatPaintInput, ChatPaintOutput

if TYPE_CHECKING:
    from ..runtime.runtime import UIRuntime


def register(mcp: Any, get_runtime: Callable[[], "UIRuntime"]) -> None:
    """Register the inline-chat free-form A2UI paint tool."""
    del get_runtime

    @mcp.tool()
    @operational(input_model=ChatPaintInput, output_model=ChatPaintOutput)
    def ui_paint_chat(payload: Any, name: Any = None) -> ToolResult[ChatPaintOutput]:
        """Paint a free-form A2UI block inline in the chat panel.

        Successful ``data`` remains the bare ``{components, name}`` carrier;
        it deliberately has no canvas sentinel. Invalid inputs are failures.
        """
        if isinstance(payload, dict) and isinstance(payload.get("components"), list):
            payload = {**payload, "components": lift_props_children(payload["components"])}
        error = _error_for_payload(payload)
        if error:
            return fail(error)
        if name is not None and not isinstance(name, str):
            return fail("name must be a string or null")
        assert isinstance(payload, dict)
        components = payload.get("components", [])
        payload_name = payload.get("name")
        if payload_name is not None and not isinstance(payload_name, str):
            return fail("payload.name must be a string")
        return ChatPaintOutput(
            components=components, name=name or payload_name or "Inline View",
        )

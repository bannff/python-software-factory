"""Agent-to-canvas A2UI paint carrier."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, fail, operational

from .paint_canvas_lift import lift_props_children
from .paint_dtos import CanvasPaintInput, CanvasPaintOutput

if TYPE_CHECKING:
    from ..runtime.runtime import UIRuntime

_VALID_TARGETS = ("graph", "timeline", "findings", "live")
_VALID_MODES = ("snapshot", "delta")


def _error_for_payload(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return "payload must be an object with a 'components' array"
    from ..runtime.a2ui import COMPONENT_CATALOG, validate_a2ui

    errors = validate_a2ui(payload)
    if errors:
        return f"Invalid A2UI payload: {errors[0].path}: {errors[0].message}"
    catalog = {name.lower().replace("_", "") for name in COMPONENT_CATALOG}
    for component in payload.get("components", []):
        if isinstance(component, dict) and isinstance(component.get("type"), str):
            if component["type"].lower().replace("_", "") not in catalog:
                valid = ", ".join(sorted(COMPONENT_CATALOG))
                return f"Unknown component type {component['type']!r}; valid types: {valid}"
    return None


def register(mcp: Any, get_runtime: Callable[[], "UIRuntime"]) -> None:
    """Register the canvas-paint operational tool."""
    del get_runtime

    @mcp.tool()
    @operational(input_model=CanvasPaintInput, output_model=CanvasPaintOutput)
    def ui_paint_canvas(
        target: Any, payload: Any, mode: Any = "snapshot",
    ) -> ToolResult[CanvasPaintOutput]:
        """Paint A2UI components onto a Companion-X canvas tab.

        The successful ``data`` field preserves the carrier's exact
        ``_a2ui_canvas`` sentinel map. Invalid inputs return a failed v1
        ToolResult so an agent can self-correct without ending the chat run.
        """
        if target not in _VALID_TARGETS:
            return fail(f"Invalid target {target!r}; expected one of {_VALID_TARGETS}. "
                        "The 'live' slot is the un-typed escape hatch for the Live tab.")
        if mode not in _VALID_MODES:
            return fail(f"Invalid mode {mode!r}; expected one of {_VALID_MODES}")
        if isinstance(payload, dict) and isinstance(payload.get("components"), list):
            payload = {**payload, "components": lift_props_children(payload["components"])}
        error = _error_for_payload(payload)
        if error:
            return fail(error)
        assert isinstance(payload, dict)
        components = payload.get("components", [])
        return CanvasPaintOutput(
            _a2ui_canvas={
                "target": target, "mode": mode,
                "payload": {"components": components, "name": payload.get("name", target)},
            },
            rendered=True, target=target, mode=mode, component_count=len(components),
        )

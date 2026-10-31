"""Deterministic global-canvas authorization for frontend deep links.

``ui_resolve_canvas`` is an authorization/allowlist check for globally
authenticated Canvas views (not owner-specific content): it requires a nonempty
ambient ``tenant_id`` + ``principal_id`` and a ``view_id`` inside the closed
:data:`CANVAS_VIEW_IDS` allowlist, and returns only ``{view_id, authorized}`` —
it never renders view content. Any unknown or malformed id, or absent/incomplete
authority, returns one fixed opaque ``canvas_view_not_found`` failure and never
echoes the input.
"""
from __future__ import annotations

from typing import Any, Callable, Literal, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import (
    ToolResult, deterministic, fail, get_envelope, ok,
)
from factory.mcp_utils.registration import typed_tool

from ..runtime.canvas_views import CANVAS_VIEW_IDS

if TYPE_CHECKING:
    from ..runtime.runtime import UIRuntime

_ERROR = "canvas_view_not_found"


class _DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CanvasResolveInput(_DTO):
    # Bounded token only; membership is checked inside the handler so an unknown
    # id returns the fixed opaque failure instead of raising/echoing at ingress.
    view_id: str = Field(min_length=1, max_length=256)


class CanvasResolveOutput(_DTO):
    authorized: Literal[True] = True
    view_id: str


def register(mcp: Any, get_runtime: Callable[[], "UIRuntime"]) -> None:
    """Register the global-canvas authorization tool."""

    @typed_tool(mcp)
    @deterministic(input_model=CanvasResolveInput, output_model=CanvasResolveOutput)
    def ui_resolve_canvas(view_id: str) -> ToolResult[CanvasResolveOutput]:
        """Authorize a globally-registered Canvas view for the ambient owner."""
        envelope = get_envelope()
        if not isinstance(envelope, dict):
            return fail(_ERROR)
        tenant = envelope.get("tenant_id")
        principal = envelope.get("principal_id")
        if not (isinstance(tenant, str) and tenant
                and isinstance(principal, str) and principal):
            return fail(_ERROR)
        if view_id not in CANVAS_VIEW_IDS:
            return fail(_ERROR)
        return ok(CanvasResolveOutput(view_id=view_id))


__all__ = ["CanvasResolveInput", "CanvasResolveOutput", "register"]

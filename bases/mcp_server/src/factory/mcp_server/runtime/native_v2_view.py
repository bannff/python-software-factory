"""Compose a native MCP-v2 callback server from the gateway selection."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import NativeMCPV2Composer, ServerCompositionPlan

from .selected_tools import native_registrations, resolve_selected_tools


def build_native_v2_view(
    aggregator: Any,
    plan: ServerCompositionPlan,
    allowlist: set[str] | None = None,
    *,
    rename_dot_to_underscore: bool = True,
) -> Any:
    """Compose the gateway's selected typed handlers through public v2 callbacks.

    The caller supplies the already sealed surface plan, so its selected-tools
    invariant is enforced by ``NativeMCPV2Composer``.  This factory has no
    FastMCP fallback: callers fail closed until the active artifact resolves
    a public MCP-v2 SDK.
    """
    selected = resolve_selected_tools(
        aggregator,
        allowlist,
        rename_dot_to_underscore=rename_dot_to_underscore,
    )
    return NativeMCPV2Composer(plan, native_registrations(selected)).compose()


__all__ = ["build_native_v2_view"]

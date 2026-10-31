"""Deterministic owner-scoped deep-link target resolver.

``notification_inbox_resolve_target`` derives tenant/owner from the ambient
envelope only, owner-scoped reads the inbox record, then re-checks ambient
authority against the owning source brick through the caller-bound MCP invoker
(no service binding kwargs) under the owner's ambient envelope. It returns only
the existing typed closed target on a valid successful source response; every
deviation — absent/foreign record, deleted/foreign/malformed source, transport
failure, unexpected payload, unsupported target, or invoker absence — collapses
to exactly one fixed opaque ``notification_target_not_found`` failure. No source
payload, URL, or route is ever returned.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from factory.mcp_utils.interface import (
    ToolResult, deterministic, fail, get_envelope, get_service, ok,
)
from factory.mcp_utils.registration import typed_tool

from .contracts.inbox_resolve import InboxResolveInput, InboxResolveOutput
from .inbox_support import inbox_authority
from ..runtime.inbox_resolve import authorize_target

if TYPE_CHECKING:
    from ..runtime.dispatcher import NotificationRuntime

_ERROR = "notification_target_not_found"


def register(mcp: Any, runtime: "NotificationRuntime") -> None:
    """Register the owner-scoped deep-link target resolver tool."""

    @typed_tool(mcp)
    @deterministic(input_model=InboxResolveInput, output_model=InboxResolveOutput)
    def inbox_resolve_target(
        notification_id: str,
    ) -> ToolResult[InboxResolveOutput]:
        """Resolve an inbox notification to its authorized closed target."""
        parsed = InboxResolveInput.model_validate(
            {"notification_id": notification_id})
        try:
            tenant, owner = inbox_authority()
            record = runtime.inbox_get(tenant, owner, parsed.notification_id)
            authorize_target(
                record.target,
                invoker_factory=get_service("tool_invoker_for_caller"),
                envelope=dict(get_envelope() or {}),
                idempotency_key=parsed.notification_id,
            )
            return ok(InboxResolveOutput(target=record.target))
        except Exception:  # noqa: BLE001 — one fixed opaque failure, no detail
            return fail(_ERROR)


__all__ = ["register"]

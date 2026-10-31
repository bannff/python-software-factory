"""Deterministic owner-scoped inbox read tools (list, get)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from .contracts.inbox_inputs import InboxGetInput, InboxListInput
from .contracts.inbox_outputs import InboxListOutput, InboxNotificationOutput
from .inbox_support import inbox_result

if TYPE_CHECKING:
    from ..runtime.dispatcher import NotificationRuntime


def register(mcp: Any, runtime: "NotificationRuntime") -> None:
    """Register read-only inbox tools with strict ingress and typed egress."""

    @typed_tool(mcp)
    @deterministic(input_model=InboxListInput, output_model=InboxListOutput)
    def inbox_list(
        limit: int = 50, offset: int = 0, unread_only: bool = False,
    ) -> ToolResult[InboxListOutput]:
        """List the caller's notifications newest-first with bounded paging."""
        parsed = InboxListInput.model_validate(
            {"limit": limit, "offset": offset, "unread_only": unread_only})

        def build(tenant: str, owner: str) -> InboxListOutput:
            records = runtime.inbox_list(
                tenant, owner, limit=parsed.limit, offset=parsed.offset,
                unread_only=parsed.unread_only)
            return InboxListOutput(notifications=records, count=len(records))

        return inbox_result(build)

    @typed_tool(mcp)
    @deterministic(input_model=InboxGetInput, output_model=InboxNotificationOutput)
    def inbox_get(notification_id: str) -> ToolResult[InboxNotificationOutput]:
        """Fetch one owner-scoped notification; foreign/absent is opaque."""
        parsed = InboxGetInput.model_validate({"notification_id": notification_id})
        return inbox_result(lambda tenant, owner: InboxNotificationOutput(
            notification=runtime.inbox_get(tenant, owner, parsed.notification_id)))


__all__ = ["register"]

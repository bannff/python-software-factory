"""Operational owner-scoped inbox mark tools (mark-read, mark-all-read).

No public create tool is exposed yet — producer projection lands next.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .contracts.inbox_inputs import InboxMarkAllReadInput, InboxMarkReadInput
from .contracts.inbox_outputs import InboxMarkAllReadOutput, InboxNotificationOutput
from .inbox_support import inbox_result

if TYPE_CHECKING:
    from ..runtime.dispatcher import NotificationRuntime


def register(mcp: Any, runtime: "NotificationRuntime") -> None:
    """Register mark tools with strict ingress, CAS fences, and typed egress."""

    @typed_tool(mcp)
    @operational(input_model=InboxMarkReadInput, output_model=InboxNotificationOutput)
    def inbox_mark_read(
        notification_id: str, expected_revision: int,
    ) -> ToolResult[InboxNotificationOutput]:
        """Revision-CAS mark one notification read; stale/foreign is a fixed code."""
        parsed = InboxMarkReadInput.model_validate(
            {"notification_id": notification_id, "expected_revision": expected_revision})
        return inbox_result(lambda tenant, owner: InboxNotificationOutput(
            notification=runtime.inbox_mark_read(
                tenant, owner, parsed.notification_id,
                expected_revision=parsed.expected_revision)))

    @typed_tool(mcp)
    @operational(input_model=InboxMarkAllReadInput, output_model=InboxMarkAllReadOutput)
    def inbox_mark_all_read(
        expected_unread_count: int,
    ) -> ToolResult[InboxMarkAllReadOutput]:
        """Count-fenced mark-all-read; a drifted count is a fixed conflict, no partial."""
        parsed = InboxMarkAllReadInput.model_validate(
            {"expected_unread_count": expected_unread_count})
        return inbox_result(lambda tenant, owner: InboxMarkAllReadOutput(
            marked_count=runtime.inbox_mark_all_read(
                tenant, owner, expected_unread_count=parsed.expected_unread_count)))


__all__ = ["register"]

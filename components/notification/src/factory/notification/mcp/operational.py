"""Strict typed operational MCP tools for Notification."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .contracts.inputs import DeliveryStatusInput, ListDeliveriesInput, SendNotificationInput
from .contracts.outputs import DeliveriesOutput, DeliveryOutput, DeliveryStatusOutput, SendNotificationOutput

if TYPE_CHECKING:
    from ..runtime.dispatcher import NotificationRuntime

_SAFE_FAILURE = "notification_operation_failed"


def _delivery(data: dict[str, Any], *, error: str | None = None) -> DeliveryOutput:
    values = {key: data.get(key) for key in DeliveryOutput.model_fields}
    values["error"] = error
    return DeliveryOutput.model_validate(values)


def register(mcp: Any, runtime: "NotificationRuntime") -> None:
    """Register operational tools with strict flat ingress and typed egress."""

    @typed_tool(mcp)
    @operational(input_model=SendNotificationInput, output_model=SendNotificationOutput)
    async def send_notification(
        recipient: str, content: str | None = None, subject: str | None = None,
        template_id: str | None = None, channel_id: str | None = None,
        data: dict[str, Any] | None = None, priority: str = "normal",
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SendNotificationOutput]:
        """Send a notification; expected provider failures remain typed data."""
        parsed = SendNotificationInput.model_validate({
            "recipient": recipient, "content": content, "subject": subject,
            "template_id": template_id, "channel_id": channel_id, "data": data,
            "priority": priority, "envelope": envelope,
        })
        try:
            result = await runtime.send_notification(
                parsed.recipient, parsed.content, parsed.subject, parsed.template_id,
                parsed.channel_id, parsed.data, parsed.priority,
            )
            sent = bool(result.get("ok")) and result.get("status") != "failed"
            return ToolResult(ok=True, data=SendNotificationOutput(
                sent=sent,
                **_delivery(result, error=None if sent else "provider_failed").model_dump(),
            ))
        except Exception:
            return ToolResult(ok=False, error=_SAFE_FAILURE)

    @typed_tool(mcp)
    @operational(input_model=DeliveryStatusInput, output_model=DeliveryStatusOutput)
    def get_delivery_status(message_id: str) -> ToolResult[DeliveryStatusOutput]:
        """Get delivery status; an absent delivery is a normal typed miss."""
        parsed = DeliveryStatusInput.model_validate({"message_id": message_id})
        try:
            result = runtime.get_delivery_status(parsed.message_id)
            return ToolResult(ok=True, data=DeliveryStatusOutput(
                found=bool(result.get("ok")),
                **_delivery(result, error=None if result.get("ok") else "not_found").model_dump(),
            ))
        except Exception:
            return ToolResult(ok=False, error=_SAFE_FAILURE)

    @typed_tool(mcp)
    @operational(input_model=ListDeliveriesInput, output_model=DeliveriesOutput)
    def list_deliveries(
        status: str | None = None, limit: int = 100, offset: int = 0,
    ) -> ToolResult[DeliveriesOutput]:
        """List deliveries with optional typed status filtering."""
        parsed = ListDeliveriesInput.model_validate({
            "status": status, "limit": limit, "offset": offset,
        })
        try:
            result = runtime.list_deliveries(parsed.status, parsed.limit, parsed.offset)
            deliveries = [_delivery(item, error=("provider_failed" if item.get("status") == "failed" else None)) for item in result["deliveries"]]
            return ToolResult(ok=True, data=DeliveriesOutput(deliveries=deliveries, count=len(deliveries)))
        except Exception:
            return ToolResult(ok=False, error=_SAFE_FAILURE)

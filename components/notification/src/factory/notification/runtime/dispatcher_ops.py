"""Notification dispatcher operations."""

from __future__ import annotations

from typing import Any

from factory.notification.runtime.models import NotificationRequest
from factory.notification.runtime.templates import render_template


class DispatcherOperations:
    """Operational methods for notification dispatcher."""

    def __init__(self, runtime: Any):
        self._runtime = runtime

    async def send_notification(
        self, recipient: str, content: str | None = None, subject: str | None = None,
        template_id: str | None = None, channel_id: str | None = None,
        data: dict[str, Any] | None = None, priority: str = "normal",
    ) -> dict[str, Any]:
        """Send a notification."""
        if not self._runtime.backend:
            return {"ok": False, "error": "Runtime not initialized"}

        final_content = content
        final_subject = subject

        if template_id and self._runtime.templates:
            template = self._runtime.templates.get(template_id)
            if template:
                rendered = render_template(template, data or {})
                final_content = rendered["body"]
                final_subject = rendered["subject"] or subject

        request = NotificationRequest(
            recipient=recipient, content=final_content, subject=final_subject,
            channel_id=channel_id, template_id=template_id,
            data=data or {}, priority=priority,
        )

        status = await self._runtime.backend.send(request)
        status.recipient = recipient
        status.channel_id = channel_id
        self._runtime.delivery_store.save(status)

        return {"ok": True, **status.to_dict()}

    def get_delivery_status(self, message_id: str) -> dict[str, Any]:
        """Get delivery status by message ID."""
        status = self._runtime.delivery_store.get(message_id)
        if not status:
            return {"ok": False, "error": "Message not found"}
        return {"ok": True, **status.to_dict()}

    def list_deliveries(
        self, status: str | None = None, limit: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        """List deliveries with optional filtering."""
        deliveries = self._runtime.delivery_store.list(status=status, limit=limit, offset=offset)
        return {"ok": True, "deliveries": [d.to_dict() for d in deliveries], "count": len(deliveries)}

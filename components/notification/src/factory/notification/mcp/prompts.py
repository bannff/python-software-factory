"""MCP prompts for notification module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

from .templates import (
    get_configure_channel_prompt,
    get_debug_delivery_prompt,
    get_create_template_prompt,
)

if TYPE_CHECKING:
    from ..runtime.dispatcher import NotificationRuntime


def register(mcp: Any, runtime: "NotificationRuntime") -> None:
    """Register MCP prompts for notification."""

    @mcp.prompt()
    def configure_channel(
        channel_id: str = "my_channel",
        channel_type: str = "smtp",
    ) -> str:
        """Guide for configuring a notification channel.

        Args:
            channel_id: Unique channel identifier
            channel_type: Type of channel (smtp, twilio, slack, webhook, console)
        """
        return get_configure_channel_prompt(channel_id, channel_type)

    @mcp.prompt()
    def debug_delivery(
        message_id: str = "msg_xxx",
        status: str = "failed",
        backend: str = "smtp",
    ) -> str:
        """Guide for debugging notification delivery issues.

        Args:
            message_id: The message ID to debug
            status: Current delivery status
            backend: Backend that handled the delivery
        """
        return get_debug_delivery_prompt(message_id, status, backend)

    @mcp.prompt()
    def create_template(
        template_id: str = "welcome",
        name: str = "Welcome Email",
    ) -> str:
        """Guide for creating a notification template.

        Args:
            template_id: Unique template identifier
            name: Human-readable template name
        """
        return get_create_template_prompt(template_id, name)

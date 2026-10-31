"""MCP resources for notification module."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING


from .docs import DOCS, get_doc, list_docs
from ..runtime.models import NotificationEnvelope, NotificationRequest, DeliveryStatus

if TYPE_CHECKING:
    from ..runtime.dispatcher import NotificationRuntime


def register(mcp: Any, runtime: "NotificationRuntime") -> None:
    """Register MCP resources for notification."""

    # Schema resources
    @mcp.resource("notification://schemas/envelope")
    def get_envelope_schema() -> str:
        """JSON schema for notification envelope."""
        return json.dumps(NotificationEnvelope.model_json_schema(), indent=2)

    @mcp.resource("notification://schemas/request")
    def get_request_schema() -> str:
        """JSON schema for notification request."""
        return json.dumps(NotificationRequest.model_json_schema(), indent=2)

    @mcp.resource("notification://schemas/delivery-status")
    def get_delivery_status_schema() -> str:
        """JSON schema for delivery status."""
        return json.dumps(DeliveryStatus.model_json_schema(), indent=2)

    # Documentation resources
    @mcp.resource("notification://docs")
    def list_documentation() -> str:
        """List available documentation."""
        return json.dumps({
            "available_docs": list_docs(),
            "access_pattern": "notification://docs/{doc_name}",
        }, indent=2)

    @mcp.resource("notification://docs/overview")
    def get_overview_doc() -> str:
        """Overview documentation."""
        return get_doc("overview") or "Documentation not found"

    @mcp.resource("notification://docs/channels")
    def get_channels_doc() -> str:
        """Channels documentation."""
        return get_doc("channels") or "Documentation not found"

    @mcp.resource("notification://docs/templates")
    def get_templates_doc() -> str:
        """Templates documentation."""
        return get_doc("templates") or "Documentation not found"

    @mcp.resource("notification://docs/envelope")
    def get_envelope_doc() -> str:
        """Envelope documentation."""
        return get_doc("envelope") or "Documentation not found"

    # Live data resources
    @mcp.resource("notification://channels")
    def get_channels_list() -> str:
        """List configured notification channels."""
        channels = runtime.get_channel_registry()
        return json.dumps({
            "channels": channels,
            "count": len(channels),
        }, indent=2)

    @mcp.resource("notification://templates")
    def get_templates_list() -> str:
        """List notification templates."""
        templates = runtime.get_template_registry()
        return json.dumps({
            "templates": templates,
            "count": len(templates),
        }, indent=2)

    @mcp.resource("notification://deliveries")
    def get_recent_deliveries() -> str:
        """List recent deliveries."""
        result = runtime.list_deliveries(limit=50)
        return json.dumps(result, indent=2, default=str)

    # Factory cross-reference
    @mcp.resource("notification://factory")
    def get_factory_reference() -> str:
        """Cross-reference to factory foreman."""
        return json.dumps({
            "brick": "notification",
            "namespace": "factory.notification",
            "foreman_tools": [
                "foreman_info",
                "foreman_check",
                "foreman_guardian_check",
            ],
            "related_bricks": [
                {"name": "events", "purpose": "Notification event streaming"},
                {"name": "workflow", "purpose": "Notification workflow triggers"},
                {"name": "auth", "purpose": "Sender authentication"},
            ],
        }, indent=2)

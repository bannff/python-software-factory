import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any
from ..models import NotificationRequest, DeliveryStatus
from .base import NotificationBackend

logger = logging.getLogger(__name__)


class StdioBackend(NotificationBackend):
    """
    A simple backend that prints notifications to stdout/logger.
    Useful for local development and debugging.
    """

    @property
    def name(self) -> str:
        return "stdio"

    async def initialize(self, config: Dict[str, Any]) -> None:
        self.prefix = config.get("prefix", "[NOTIFICATION]")

    async def send(self, request: NotificationRequest) -> DeliveryStatus:
        message_id = str(uuid.uuid4())

        # In a real app, we might render templates here.
        # For now, we just dump the request.
        payload = {
            "recipient": request.recipient,
            "content": request.content,
            "template_id": request.template_id,
            "data": request.data,
            "priority": request.priority,
        }

        # Print to stdout (or log)
        # Note: In MCP, we must be careful not to corrupt the stdio transport.
        # So we use stderr or a file logger in a real scenario, or just return status.
        # Here we simulated "sending" by logging.
        logger.info(f"{self.prefix} {json.dumps(payload)}")

        return DeliveryStatus(
            message_id=message_id,
            status="sent",
            backend=self.name,
            timestamp=datetime.now(timezone.utc),
        )

    async def health_check(self) -> bool:
        return True

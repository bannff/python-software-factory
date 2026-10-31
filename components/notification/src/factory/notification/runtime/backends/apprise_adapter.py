"""Apprise-backed notification backend.

Delegates to the `apprise` library which supports 100+ notification
services (Slack, Discord, email/SMTP, Telegram, PushOver, etc.).
URLs follow the Apprise URL schema: https://github.com/caronc/apprise/wiki
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import apprise

from ..models import DeliveryStatus, NotificationRequest
from .base import NotificationBackend

logger = logging.getLogger(__name__)


class AppriseBackend(NotificationBackend):
    """Notification backend powered by Apprise.

    Config keys:
        urls: list[str]  — Apprise service URLs to deliver to.
    """

    def __init__(self) -> None:
        self._ap: apprise.Apprise | None = None

    @property
    def name(self) -> str:
        return "apprise"

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize with a list of Apprise service URLs."""
        self._ap = apprise.Apprise()
        urls: list[str] = config.get("urls", [])
        for url in urls:
            self._ap.add(url)

    async def send(self, request: NotificationRequest) -> DeliveryStatus:
        """Send notification via all configured Apprise services."""
        message_id = str(uuid.uuid4())
        if not self._ap:
            return DeliveryStatus(
                message_id=message_id,
                status="failed",
                backend=self.name,
                error="Backend not initialized",
            )

        body = request.content or ""
        title = request.subject or ""

        ok = self._ap.notify(body=body, title=title)

        return DeliveryStatus(
            message_id=message_id,
            status="sent" if ok else "failed",
            backend=self.name,
            timestamp=datetime.now(timezone.utc),
            error=None if ok else "Apprise delivery failed",
        )

    async def health_check(self) -> bool:
        """Healthy if at least one service URL is configured."""
        return self._ap is not None and len(self._ap) > 0

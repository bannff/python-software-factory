"""Delivery tracking and storage."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from factory.notification.runtime.models import DeliveryStatus


class DeliveryStore(ABC):
    """Protocol for delivery status storage."""

    @abstractmethod
    def save(self, status: DeliveryStatus) -> None:
        """Save or update delivery status."""
        pass

    @abstractmethod
    def get(self, message_id: str) -> DeliveryStatus | None:
        """Get delivery status by message ID."""
        pass

    @abstractmethod
    def list(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DeliveryStatus]:
        """List deliveries with optional filtering."""
        pass


class InMemoryDeliveryStore(DeliveryStore):
    """In-memory delivery store for local development."""

    def __init__(self):
        self._deliveries: dict[str, DeliveryStatus] = {}

    def save(self, status: DeliveryStatus) -> None:
        """Save or update delivery status."""
        self._deliveries[status.message_id] = status

    def get(self, message_id: str) -> DeliveryStatus | None:
        """Get delivery status by message ID."""
        return self._deliveries.get(message_id)

    def list(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DeliveryStatus]:
        """List deliveries with optional filtering."""
        deliveries = list(self._deliveries.values())
        
        if status:
            deliveries = [d for d in deliveries if d.status == status]
        
        # Sort by timestamp descending
        deliveries.sort(key=lambda d: d.timestamp, reverse=True)
        
        return deliveries[offset:offset + limit]

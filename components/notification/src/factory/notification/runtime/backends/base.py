from abc import ABC, abstractmethod
from typing import Dict, Any
from ..models import NotificationRequest, DeliveryStatus


class NotificationBackend(ABC):
    """Protocol for notification backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of the backend."""
        pass

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the backend with configuration."""
        pass

    @abstractmethod
    async def send(self, request: NotificationRequest) -> DeliveryStatus:
        """Dispatch a notification."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if backend is healthy."""
        pass

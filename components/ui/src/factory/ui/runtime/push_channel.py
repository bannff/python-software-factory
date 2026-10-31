"""Push channel for real-time UI updates to connected clients."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable

from .models import ViewUpdate

logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    """Types of push channels."""

    WEBSOCKET = "websocket"
    SSE = "sse"
    CALLBACK = "callback"


@dataclass
class ClientConnection:
    """Represents a connected client."""

    client_id: str
    channel_type: ChannelType
    subscribed_views: set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    # For callback-based connections
    callback: Callable[[ViewUpdate], Awaitable[None]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "client_id": self.client_id,
            "channel_type": self.channel_type.value,
            "subscribed_views": list(self.subscribed_views),
            "connected_at": self.connected_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "metadata": self.metadata,
        }


class PushChannel:
    """Manages real-time push updates to connected UI clients.

    This is the core mechanism for agent-driven UI updates.
    When an agent modifies a view, the PushChannel broadcasts
    the update to all subscribed clients.
    """

    def __init__(self) -> None:
        self._clients: dict[str, ClientConnection] = {}
        self._queues: dict[str, asyncio.Queue[ViewUpdate]] = {}
        self._broadcast_callbacks: list[Callable[[ViewUpdate], Awaitable[None]]] = []

    def connect(
        self,
        client_id: str,
        channel_type: ChannelType = ChannelType.CALLBACK,
        callback: Callable[[ViewUpdate], Awaitable[None]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ClientConnection:
        """Register a new client connection."""
        connection = ClientConnection(
            client_id=client_id,
            channel_type=channel_type,
            callback=callback,
            metadata=metadata or {},
        )
        self._clients[client_id] = connection
        self._queues[client_id] = asyncio.Queue()
        logger.info(f"Client connected: {client_id} ({channel_type.value})")
        return connection

    def disconnect(self, client_id: str) -> bool:
        """Disconnect a client."""
        if client_id in self._clients:
            del self._clients[client_id]
            del self._queues[client_id]
            logger.info(f"Client disconnected: {client_id}")
            return True
        return False

    def subscribe(self, client_id: str, view_id: str) -> bool:
        """Subscribe a client to view updates."""
        if client_id in self._clients:
            self._clients[client_id].subscribed_views.add(view_id)
            self._clients[client_id].last_activity = datetime.now(timezone.utc)
            logger.debug(f"Client {client_id} subscribed to view {view_id}")
            return True
        return False

    def unsubscribe(self, client_id: str, view_id: str) -> bool:
        """Unsubscribe a client from view updates."""
        if client_id in self._clients:
            self._clients[client_id].subscribed_views.discard(view_id)
            self._clients[client_id].last_activity = datetime.now(timezone.utc)
            return True
        return False

    async def push(self, update: ViewUpdate) -> int:
        """Push an update to all subscribed clients.

        Returns the number of clients that received the update.
        """
        recipients = 0

        for client_id, connection in self._clients.items():
            # Check if client is subscribed to this view (or subscribed to "*" for all)
            if update.view_id in connection.subscribed_views or "*" in connection.subscribed_views:
                try:
                    if connection.callback:
                        await connection.callback(update)
                    else:
                        await self._queues[client_id].put(update)
                    connection.last_activity = datetime.now(timezone.utc)
                    recipients += 1
                except Exception as e:
                    logger.error(f"Failed to push to client {client_id}: {e}")

        # Also call broadcast callbacks
        for callback in self._broadcast_callbacks:
            try:
                await callback(update)
            except Exception as e:
                logger.error(f"Broadcast callback failed: {e}")

        logger.debug(f"Pushed update for view {update.view_id} to {recipients} clients")
        return recipients

    async def get_update(self, client_id: str, timeout: float | None = None) -> ViewUpdate | None:
        """Get the next update for a client (for polling/SSE)."""
        if client_id not in self._queues:
            return None
        try:
            if timeout:
                return await asyncio.wait_for(self._queues[client_id].get(), timeout)
            return await self._queues[client_id].get()
        except asyncio.TimeoutError:
            return None

    def add_broadcast_callback(self, callback: Callable[[ViewUpdate], Awaitable[None]]) -> None:
        """Add a callback that receives all updates."""
        self._broadcast_callbacks.append(callback)

    def remove_broadcast_callback(self, callback: Callable[[ViewUpdate], Awaitable[None]]) -> None:
        """Remove a broadcast callback."""
        if callback in self._broadcast_callbacks:
            self._broadcast_callbacks.remove(callback)

    def get_client(self, client_id: str) -> ClientConnection | None:
        """Get a client connection."""
        return self._clients.get(client_id)

    def list_clients(self) -> list[ClientConnection]:
        """List all connected clients."""
        return list(self._clients.values())

    def get_subscribers(self, view_id: str) -> list[ClientConnection]:
        """Get all clients subscribed to a view."""
        return [
            c
            for c in self._clients.values()
            if view_id in c.subscribed_views or "*" in c.subscribed_views
        ]

    def to_dict(self) -> dict[str, Any]:
        """Export channel state."""
        return {
            "connected_clients": len(self._clients),
            "clients": [c.to_dict() for c in self._clients.values()],
        }

"""Polylith Interface for notification module."""

from .server import create_mcp_server as create_server
from .runtime.dispatcher import NotificationRuntime as Runtime

__all__ = ["Runtime", "create_server"]

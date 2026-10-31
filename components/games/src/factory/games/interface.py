"""Polylith Interface for games module."""

from .server import create_mcp_server as create_server
from .runtime.runtime import GamesRuntime as Runtime

__all__ = ["Runtime", "create_server"]

"""Polylith interface for cache brick."""

from .server import create_mcp_server as create_server
from .runtime import runtime

__all__ = ["create_server", "runtime"]

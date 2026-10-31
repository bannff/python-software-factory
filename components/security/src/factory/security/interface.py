"""Polylith Interface for security module."""

from .runtime.runtime import SecurityRuntime as Runtime
from .server import create_mcp_server as create_server

__all__ = ["Runtime", "create_server"]

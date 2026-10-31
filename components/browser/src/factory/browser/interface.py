"""Polylith Interface for browser module."""

from .runtime.runtime import BrowserRuntime as Runtime
from .server import create_mcp_server as create_server

__all__ = ["Runtime", "create_server"]

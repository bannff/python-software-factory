"""Polylith interface for the KB brick."""

from .runtime.runtime import KBRuntime as Runtime
from .server import create_mcp_server as create_server

__all__ = ["Runtime", "create_server"]

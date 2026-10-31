"""Polylith Interface for the domain module."""

from .server import create_mcp_server as create_server, get_runtime as default_runtime
from .runtime.runtime import DomainRuntime as Runtime

__all__ = ["Runtime", "create_server", "default_runtime"]

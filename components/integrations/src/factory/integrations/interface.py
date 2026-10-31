"""Polylith interface for integrations brick."""

from factory.integrations.runtime.runtime import IntegrationsRuntime as Runtime
from factory.integrations.server import create_mcp_server as create_server

__all__ = ["Runtime", "create_server"]

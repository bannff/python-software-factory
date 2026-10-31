"""Polylith Interface for logger module.

Public API:
- server: MCP server instance
- LoggerRuntime: Main runtime class
- LogRecord, LogLevel: Core types
"""

from .server import create_mcp_server as create_server
from .runtime.runtime import LoggerRuntime
from .runtime.ports import LogRecord, LogLevel, LogSink, LogFormatter

__all__ = [
    "create_server",
    "LoggerRuntime",
    "LogRecord",
    "LogLevel",
    "LogSink",
    "LogFormatter",
]

"""Public interface for the Terminal brick."""
from .runtime.models import (
    TerminalCompletionEntry, TerminalCompletionResult, TerminalCompletionSpec,
    TerminalOutputChunk, TerminalSessionRef, TerminalSpawnSpec,
)
from .runtime.runtime import TerminalRuntime, get_runtime
from .server import create_mcp_server as create_server

__all__ = [
    "TerminalCompletionEntry", "TerminalCompletionResult", "TerminalCompletionSpec",
    "TerminalOutputChunk", "TerminalRuntime", "TerminalSessionRef",
    "TerminalSpawnSpec", "create_server", "get_runtime",
]

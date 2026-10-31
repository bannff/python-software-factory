"""Polylith Interface for the oracle module.

Public API: the MCP server factory, the runtime, and the pack-facing
verifier-registration seam (``register_verifier`` / ``get_registry``) so a
domain pack can contribute a verifier WITHOUT the oracle engine ever
importing the pack.
"""

from .server import create_mcp_server as create_server
from .runtime.runtime import OracleRuntime as Runtime
from .runtime.registry import register_verifier, get_registry, reset_registry
from .runtime.ports import VerifierPort

__all__ = [
    "Runtime",
    "create_server",
    "register_verifier",
    "get_registry",
    "reset_registry",
    "VerifierPort",
]

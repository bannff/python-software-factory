"""Authoring (security-gated) MCP tools for the oracle brick.

The oracle ships no authoring tools today — verifier registration is a
code/pack seam (``factory.oracle.interface.register_verifier``), not a
runtime-mutable config surface. This module exists for brick-anatomy
parity and as the docking point for future gated verifier management.
"""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any

if TYPE_CHECKING:
    from ..runtime.runtime import OracleRuntime


def register(mcp: Any, get_runtime: Callable[[], "OracleRuntime"]) -> None:
    """Register authoring tools (none today — gated seam reserved)."""
    return None

"""Observability hooks shared by chat / graph / swarm runtimes.

Currently houses the mcp-ui redaction filter (bd:python-factory-0x2jq).
"""
from __future__ import annotations

from .mcp_ui_redaction import (
    MCPUIRedactionFilter,
    install_mcp_ui_redaction,
    redact_mcp_ui_block,
    redact_mcp_ui_in_otel_attributes,
)

__all__ = [
    "MCPUIRedactionFilter",
    "install_mcp_ui_redaction",
    "redact_mcp_ui_block",
    "redact_mcp_ui_in_otel_attributes",
]

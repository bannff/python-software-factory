"""Aggregator access for the Neo4j ledger: one place that unwraps the envelope."""
from __future__ import annotations

from typing import Any

from ..errors import LedgerError


def _get_aggregator() -> Any:
    from factory.mcp_server.interface import get_server, get_aggregator
    # Reuse the running server's aggregator; constructing one per graph call
    # re-enters server creation from inside a request.
    agg = get_aggregator()
    if agg is None:
        get_server()
        agg = get_aggregator()
    return agg


def _unwrap(result: Any) -> Any:
    """Return the v1 envelope's ``data``; raise ``LedgerError`` on failure."""
    if not isinstance(result, dict) or "ok" not in result:
        raise LedgerError("graph_response_invalid", f"unexpected graph response: {result!r}")
    if not result["ok"]:
        raise LedgerError("graph_call_failed", str(result.get("error")))
    return result.get("data") or {}


def _invoke(tool_name: str, **kwargs: Any) -> Any:
    agg = _get_aggregator()
    if agg is None:
        raise RuntimeError("MCP aggregator not available")
    return _unwrap(agg.invoke_tool(tool_name, **kwargs))

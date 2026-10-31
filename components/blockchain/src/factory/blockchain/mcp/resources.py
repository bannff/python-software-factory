"""MCP resources for blockchain agent economy."""

from __future__ import annotations

from typing import Any

from .docs import get_doc, list_docs
from .templates import get_template, list_templates


def register(mcp: Any) -> None:
    """Register blockchain resources."""

    @mcp.resource("blockchain://docs")
    def blockchain_docs_list() -> str:
        """List blockchain documentation topics."""
        return "\n".join(
            [f"- blockchain://docs/{d}" for d in list_docs()]
        )

    @mcp.resource("blockchain://docs/{name}")
    def blockchain_doc(name: str) -> str:
        """Get blockchain documentation by topic."""
        return get_doc(name) or f"Not found. Available: {list_docs()}"

    @mcp.resource("blockchain://templates")
    def blockchain_templates_list() -> str:
        """List blockchain prompt templates."""
        return "\n".join(
            [f"- blockchain://templates/{t}" for t in list_templates()]
        )

    @mcp.resource("blockchain://templates/{name}")
    def blockchain_template(name: str) -> str:
        """Get a blockchain prompt template."""
        return get_template(name) or f"Not found. Available: {list_templates()}"

    @mcp.resource("blockchain://integration")
    def blockchain_integration() -> str:
        """How the blockchain brick integrates with other bricks."""
        return """# Blockchain Integration

| Brick | Integration |
|-------|-------------|
| graph | Neo4j adapter persists wallets, transactions, blocks, bounties as graph nodes |
| events | Transaction lifecycle events (blockchain.tx.committed, blockchain.bounty.*) |
| telemetry | Auto-instrumented OTel spans on all tool invocations |
| metrics | Economy health metrics (supply, volume, completion rates) |
| agent | Agents earn/spend tokens via bounties |
| evals | Bounty results evaluated before token release (eval-gated, shipped) |
| games | RL environments provide bounty targets (planned) |
"""

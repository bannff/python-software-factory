"""Tests for blockchain MCP contract tools.

Every MCP-enabled brick MUST expose:
- get_capabilities() - Machine-readable feature list
- health_check() - Fast readiness probe
- describe_config_schema() - JSON schema for configuration
"""

from __future__ import annotations

import asyncio

import pytest
from factory.mcp_utils.interface import ToolResult, get_service, set_service

from factory.blockchain.runtime.runtime import BlockchainRuntime
from factory.blockchain.server import create_mcp_server


def _get_tool(name: str):
    """Get a tool by name from the MCP server."""
    mcp = create_mcp_server(BlockchainRuntime())
    return asyncio.run(mcp.get_tool(name))


class TestGetCapabilities:
    def test_tool_registered(self) -> None:
        tool = _get_tool("blockchain_get_capabilities")
        assert tool is not None

    def test_returns_dict(self) -> None:
        result = _get_tool("blockchain_get_capabilities").fn()
        assert result.ok and result.data is not None

    def test_has_version(self) -> None:
        result = _get_tool("blockchain_get_capabilities").fn()
        assert result.data.version

    def test_has_features(self) -> None:
        result = _get_tool("blockchain_get_capabilities").fn()
        assert "agent_economy" in result.data.features


class TestHealthCheck:
    def test_tool_registered(self) -> None:
        assert _get_tool("blockchain_health_check") is not None

    def test_returns_healthy(self) -> None:
        result = _get_tool("blockchain_health_check").fn()
        assert result.ok and result.data.healthy is True


class TestDescribeConfigSchema:
    def test_tool_registered(self) -> None:
        assert _get_tool("blockchain_describe_config_schema") is not None

    def test_has_properties(self) -> None:
        result = _get_tool("blockchain_describe_config_schema").fn()
        assert result.ok and result.data.properties


class TestDashboardViews:
    @pytest.fixture
    def runtime(self) -> BlockchainRuntime:
        return BlockchainRuntime("mock")

    @pytest.fixture
    def mcp(self, runtime: BlockchainRuntime):
        return create_mcp_server(runtime)

    def test_dashboard_tools_registered(self, mcp) -> None:
        tool_names = [tool.name for tool in asyncio.run(mcp.list_tools())]
        assert "blockchain_get_dashboard_summary" in tool_names
        assert "blockchain_get_activity" in tool_names
        assert "blockchain_get_entity_graph_context" in tool_names
        assert "blockchain_get_views" in tool_names

    @pytest.mark.asyncio
    async def test_dashboard_summary_and_views(self, mcp, runtime: BlockchainRuntime) -> None:
        published: list[dict[str, object]] = []

        def fake_invoker(tool_name: str, **kwargs):
            if tool_name == "events_publish":
                payload = kwargs.get("payload", {})
                published.append({
                    "event_id": f"evt-{len(published) + 1}",
                    "event_type": kwargs.get("event_type", ""),
                    "source": kwargs.get("source", ""),
                    "timestamp": "2026-05-06T00:00:00+00:00",
                    "payload": payload,
                    "metadata": kwargs.get("attributes", {}),
                })
                return {"event_id": f"evt-{len(published)}", "status": "published"}
            if tool_name == "events_query_history":
                entries = list(reversed(published))
                limit = int(kwargs.get("limit", len(entries)))
                return ToolResult(data=type("History", (), {"entries": entries[:limit]})())
            if tool_name == "graph_graph_add_entity" or tool_name == "graph_graph_add_relationship":
                return {"ok": True}
            if tool_name == "graph_graph_get_entity":
                entity_id = str(kwargs.get("entity_id", ""))
                if entity_id.startswith("tx-"):
                    return {
                        "found": True,
                        "id": entity_id,
                        "type": "Transaction",
                        "properties": {"tx_id": entity_id, "tx_type": "transfer", "status": "committed"},
                    }
                if entity_id.startswith("bounty-"):
                    return {
                        "found": True,
                        "id": entity_id,
                        "type": "Bounty",
                        "properties": {"bounty_id": entity_id, "status": "open"},
                    }
                return {"found": False}
            if tool_name == "graph_graph_get_neighbors":
                entity_id = str(kwargs.get("entity_id", ""))
                if entity_id.startswith("tx-"):
                    return {
                        "entity_id": entity_id,
                        "neighbors": [
                            {"id": "wallet-alice", "type": "Wallet", "properties": {"wallet_id": "wallet-alice", "balance": 400}},
                            {"id": "wallet-bob", "type": "Wallet", "properties": {"wallet_id": "wallet-bob", "balance": 100}},
                        ],
                    }
                if entity_id.startswith("bounty-"):
                    return {
                        "entity_id": entity_id,
                        "neighbors": [
                            {"id": "workflow-run-1", "type": "WorkflowRun", "properties": {"run_id": "run-1", "status": "completed"}},
                        ],
                    }
                return {"entity_id": entity_id, "neighbors": []}
            raise AssertionError(f"unexpected tool: {tool_name}")

        previous_invoker = get_service("tool_invoker")
        set_service("tool_invoker", fake_invoker)

        try:
            ledger = runtime.get_ledger()
            ledger.create_wallet("alice", initial_balance=500)
            ledger.create_wallet("bob", initial_balance=0)
            tx = ledger.transfer("wallet-alice", "wallet-bob", 100, "reward")
            bounty = ledger.post_bounty("wallet-alice", 50, "Audit target")

            summary_tool = await mcp.get_tool("blockchain_get_dashboard_summary")
            activity_tool = await mcp.get_tool("blockchain_get_activity")
            graph_tool = await mcp.get_tool("blockchain_get_entity_graph_context")
            views_tool = await mcp.get_tool("blockchain_get_views")

            summary = summary_tool.fn().data.model_dump()
            activity = activity_tool.fn(tx_id=tx.tx_id, limit=10).data.model_dump()
            graph_context = graph_tool.fn(entity_id=tx.tx_id, limit=10).data.model_dump()
            views = views_tool.fn().data.views

            assert summary["overview"]["transactions"] >= 1
            assert summary["overview"]["bounties"] >= 1
            assert summary["overview"]["activity"] >= 1
            assert summary["overview"]["graph_entities"] >= 1
            assert any(item["tx_id"] == tx.tx_id for item in summary["transactions"])
            tx_row = next(item for item in summary["transactions"] if item["tx_id"] == tx.tx_id)
            assert tx_row["activity_count"] >= 1
            bounty_row = next(item for item in summary["bounties"] if item["bounty_id"] == bounty.bounty_id)
            assert bounty_row["activity_count"] >= 1
            assert any(item["event_type"] == "blockchain.tx.committed" for item in summary["recent_activity"])
            assert any(item["entity_type"] == "Wallet" for item in summary["related_graph_entities"])
            assert activity["count"] >= 1
            assert any(item["tx_id"] == tx.tx_id for item in activity["entries"])
            assert graph_context["count"] >= 1
            assert any(item["entity_type"] == "Wallet" for item in graph_context["entries"])

            component_ids = [component["id"] for component in views[0]["components"]]
            assert "bc-tx-mix" in component_ids
            assert "bc-transactions" in component_ids
            assert "bc-activity-stream" in component_ids
            assert "bc-graph-context" in component_ids
            assert "bc-bounties" in component_ids
        finally:
            set_service("tool_invoker", previous_invoker)

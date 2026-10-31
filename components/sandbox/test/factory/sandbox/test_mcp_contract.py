"""Tests for sandbox MCP contract compliance."""

import asyncio

import pytest
from factory.graph.mcp.core_models import EntityData, EntityLookupData, EntitySearchData, NeighborsData
from factory.mcp_utils.interface import get_service, set_service
from factory.mcp_utils.runtime.tool_result import ToolResult

from factory.sandbox.runtime.adapters.mock import MockAdapter
from factory.sandbox.runtime.runtime import SandboxRuntime
from factory.sandbox.interface import Runtime, create_server


class TestMCPContract:
    """Test MCP contract compliance."""

    @pytest.fixture
    def runtime(self) -> SandboxRuntime:
        """Create runtime with mock adapter."""
        return Runtime(MockAdapter())

    @pytest.fixture
    def mcp(self, runtime: SandboxRuntime):
        """Create MCP server."""
        return create_server(runtime)

    def test_interface_exports(self) -> None:
        """Test interface exports Runtime and create_server."""
        assert Runtime is not None
        assert create_server is not None

    def test_mcp_server_created(self, mcp) -> None:
        """Test MCP server is created."""
        assert mcp is not None
        assert mcp.name == "sandbox-module"

    def test_has_contract_tools(self, mcp) -> None:
        """Test MCP server has required contract tools."""
        tool_names = [t.name for t in asyncio.run(mcp.list_tools())]
        assert "sandbox.get_capabilities" in tool_names
        assert "sandbox.health_check" in tool_names
        assert "sandbox.describe_config_schema" in tool_names
        assert "sandbox_get_dashboard_summary" in tool_names
        assert "sandbox_get_environment_activity" in tool_names
        assert "sandbox_get_environment_graph_context" in tool_names
        assert "sandbox_get_views" in tool_names

    def test_has_operational_tools(self, mcp) -> None:
        """Test MCP server has operational tools."""
        tool_names = [t.name for t in asyncio.run(mcp.list_tools())]
        assert "sandbox.provision" in tool_names
        assert "sandbox.terminate" in tool_names
        assert "sandbox.execute" in tool_names


class TestContractToolBehavior:
    """Test contract tool behavior."""

    @pytest.fixture
    def runtime(self) -> SandboxRuntime:
        """Create runtime with mock adapter."""
        return Runtime(MockAdapter())

    @pytest.fixture
    def mcp(self, runtime: SandboxRuntime):
        """Create MCP server."""
        return create_server(runtime)

    def test_get_capabilities(self, mcp) -> None:
        """Test get_capabilities returns expected structure."""
        tool = asyncio.run(mcp.get_tool("sandbox.get_capabilities"))
        result = tool.fn()
        assert isinstance(result, ToolResult)
        assert result.data.name == "sandbox"
        assert result.data.version
        assert "tools" in result.data.model_fields_set
        assert result.data.adapters

    def test_health_check(self, mcp) -> None:
        """Test health_check returns health status."""
        tool = asyncio.run(mcp.get_tool("sandbox.health_check"))
        result = tool.fn()
        assert isinstance(result, ToolResult)
        assert result.data.healthy is True

    def test_describe_config_schema(self, mcp) -> None:
        """Test describe_config_schema returns JSON schema."""
        tool = asyncio.run(mcp.get_tool("sandbox.describe_config_schema"))
        result = tool.fn()
        assert isinstance(result, ToolResult)
        assert result.data.type == "object"
        assert "instance_type" in result.data.properties

    @pytest.mark.asyncio
    async def test_dashboard_summary_and_views(self, mcp, runtime: SandboxRuntime) -> None:
        """Dashboard summary should expose fleet data and profile catalog."""
        published: list[dict[str, object]] = []

        def _envelope(data):
            """Mirror the production tool_invoker contract: a plain dict envelope.

            ``MCPAggregator.invoke_tool`` returns ``ToolResult.model_dump()`` —
            a dict, not a ToolResult object. Serializing here keeps the fake
            honest so attribute-access reader regressions actually fail.
            """
            payload = data.model_dump(mode="json") if hasattr(data, "model_dump") else data
            return {"schema_version": "v1", "ok": True, "data": payload, "error": None}

        def fake_invoker(tool_name: str, **kwargs):
            if tool_name == "events_publish":
                payload = kwargs.get("payload", {})
                published.append({
                    "event_id": f"evt-{len(published) + 1}",
                    "event_type": kwargs.get("event_type", ""),
                    "source": kwargs.get("source", ""),
                    "timestamp": "2026-05-05T00:00:00+00:00",
                    "payload": payload,
                    "metadata": {},
                })
                return {"event_id": f"evt-{len(published)}", "status": "published"}
            if tool_name == "events_query_history":
                entries = list(reversed(published))
                source = kwargs.get("source")
                if source:
                    entries = [entry for entry in entries if entry.get("source") == source]
                payload_key = kwargs.get("payload_key")
                payload_value = kwargs.get("payload_value")
                if payload_key is not None:
                    entries = [
                        entry
                        for entry in entries
                        if str((entry.get("payload") or {}).get(payload_key)) == str(payload_value)
                    ]
                limit = int(kwargs.get("limit", len(entries)))
                return _envelope({"entries": entries[:limit], "total": len(entries[:limit])})
            if tool_name == "graph_graph_find_entities":
                return _envelope(EntitySearchData(entities=[
                    EntityData(
                        id=f"sandbox-env-{second.env_id}",
                        type="SandboxEnvironment",
                        properties={
                            "env_id": second.env_id,
                            "status": "running",
                            "profile": "webgoat",
                        },
                    ),
                ], count=1))
            if tool_name == "graph_graph_get_entity":
                entity_id = str(kwargs.get("entity_id", ""))
                if entity_id == f"sandbox-env-{second.env_id}":
                    return _envelope(EntityLookupData(
                        found=True,
                        entity_id=entity_id,
                        entity=EntityData(
                            id=entity_id,
                            type="SandboxEnvironment",
                            properties={
                                "env_id": second.env_id,
                                "status": "running",
                                "profile": "webgoat",
                            },
                        ),
                    ))
                return _envelope(EntityLookupData(found=False, entity_id=entity_id))
            if tool_name == "graph_graph_get_neighbors":
                entity_id = str(kwargs.get("entity_id", ""))
                return _envelope(NeighborsData(
                    entity_id=entity_id,
                    neighbors=[
                        EntityData(
                            id=f"workflow-run-{second.env_id}",
                            type="WorkflowRun",
                            properties={
                                "run_id": f"run-{second.env_id}",
                                "status": "completed",
                            },
                        ),
                        EntityData(
                            id=f"metric-{second.env_id}",
                            type="Metric",
                            properties={
                                "name": "sandbox.activity.count",
                                "status": "fresh",
                            },
                        ),
                    ],
                    count=2,
                ))
            raise AssertionError(f"unexpected tool: {tool_name}")

        previous_invoker = get_service("tool_invoker")
        set_service("tool_invoker", fake_invoker)

        try:
            first = await runtime.provision()
            second = await runtime.provision(profile="webgoat")
            await runtime.get_status(first.env_id)
            await runtime.get_status(second.env_id)
            await runtime.execute(second.env_id, "echo hello")

            summary_tool = await mcp.get_tool("sandbox_get_dashboard_summary")
            activity_tool = await mcp.get_tool("sandbox_get_environment_activity")
            graph_tool = await mcp.get_tool("sandbox_get_environment_graph_context")
            views_tool = await mcp.get_tool("sandbox_get_views")

            summary = summary_tool.fn().data.model_dump()
            activity = activity_tool.fn(env_id=second.env_id, limit=10).data.model_dump()
            graph_context = graph_tool.fn(env_id=second.env_id, limit=10).data.model_dump()
            views = views_tool.fn().data.views

            assert summary["overview"]["environments"] >= 2
            assert summary["overview"]["profiles"] >= 1
            assert summary["overview"]["activity"] >= 1
            assert summary["overview"]["graph_entities"] >= 1
            assert any(item["label"] == "Running" for item in summary["series"])
            assert any(item["profile_name"] == "webgoat" for item in summary["environments"])
            webgoat = next(item for item in summary["environments"] if item["env_id"] == second.env_id)
            assert webgoat["profile_health_url"] == "http://localhost:8080/WebGoat"
            assert "8080->8080" in webgoat["ports"]
            assert webgoat["activity_count"] >= 1
            assert webgoat["last_activity_type"] in {"sandbox.command_executed", "sandbox.status_observed"}
            assert any(item["name"] == "webgoat" for item in summary["profiles"])
            assert any(item["event_type"] == "sandbox.command_executed" for item in summary["recent_activity"])
            assert any(item["entity_type"] == "WorkflowRun" for item in summary["related_graph_entities"])
            assert activity["count"] >= 1
            assert any(item["event_type"] == "sandbox.command_executed" for item in activity["entries"])
            assert graph_context["count"] >= 1
            assert any(item["entity_type"] == "WorkflowRun" for item in graph_context["entries"])

            component_ids = [component["id"] for component in views[0]["components"]]
            assert "sb-status-mix" in component_ids
            assert "sb-environments" in component_ids
            assert "sb-activity-stream" in component_ids
            assert "sb-graph-context" in component_ids
            assert "sb-profiles" in component_ids
        finally:
            set_service("tool_invoker", previous_invoker)


    def test_has_authoring_tools(self, mcp) -> None:
        """Test MCP server has authoring tools."""
        tool_names = [t.name for t in asyncio.run(mcp.list_tools())]
        assert "sandbox.authoring.get_status" in tool_names
        assert "sandbox.authoring.list_templates" in tool_names
        assert "sandbox.authoring.upsert_template" in tool_names
        assert "sandbox.authoring.delete_template" in tool_names

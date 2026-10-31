"""Tests for workflow MCP contract tools.
Tests get_capabilities, health_check, and describe_config_schema.
"""
from __future__ import annotations
import asyncio
from pathlib import Path
from unittest.mock import MagicMock
import pytest
import yaml
from factory.graph.mcp.core_models import EntityData, EntityLookupData, NeighborsData
from factory.mcp_utils.runtime.tool_result import ToolResult
from factory.mcp_utils.interface import get_service, set_service
from factory.workflow.runtime.envelope import parse_envelope
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.server import create_mcp_server

class TestGetCapabilities:
    """Tests for get_capabilities contract tool."""
    def test_returns_required_fields(self) -> None:
        """Test that capabilities include required fields."""
        from factory.workflow.runtime.runtime import WorkflowRuntime
        runtime = self._create_mock_runtime()
        caps = runtime.get_capabilities()
        assert "schema_versions" in caps
        assert "supported_storage_backends" in caps
        assert "supported_executor_backends" in caps
        assert "current_executor" in caps
    def test_includes_executor_backends(self) -> None:
        """Test that supported executor backends are listed."""
        runtime = self._create_mock_runtime()
        caps = runtime.get_capabilities()
        backends = caps["supported_executor_backends"]
        assert "local" in backends
        assert "celery" in backends
        assert "dagster" in backends
    def test_includes_feature_flags(self) -> None:
        """Test that feature flags are included."""
        runtime = self._create_mock_runtime()
        caps = runtime.get_capabilities()
        assert "feature_flags" in caps
        assert "step_kinds" in caps["feature_flags"]
    def _create_mock_runtime(self) -> MagicMock:
        """Create a mock runtime with realistic capabilities."""
        runtime = MagicMock()
        runtime.get_capabilities.return_value = {
            "schema_versions": {"settings": ["v1"], "workflow_definition": ["v1"]},
            "supported_storage_backends": ["sqlite"],
            "supported_executor_backends": ["local", "celery", "dagster"],
            "current_executor": "local",
            "authoring_enabled": False,
            "running_mode": "stdio",
            "feature_flags": {"step_kinds": ["noop", "wait_for_event", "task"]},
        }
        return runtime

class TestHealthCheck:
    """Tests for health_check contract tool."""
    def test_healthy_status(self) -> None:
        """Test health check returns ok when all systems healthy."""
        runtime = self._create_mock_runtime(storage_ok=True, executor_ok=True)
        health = runtime.health_check()
        assert health["status"] == "ok"
        assert health["storage"]["ok"] is True
        assert health["executor"]["ok"] is True
    def test_degraded_status_storage_failure(self) -> None:
        """Test health check returns degraded when storage fails."""
        runtime = self._create_mock_runtime(storage_ok=False, executor_ok=True)
        health = runtime.health_check()
        assert health["status"] == "degraded"
        assert health["storage"]["ok"] is False
    def test_degraded_status_executor_failure(self) -> None:
        """Test health check returns degraded when executor fails."""
        runtime = self._create_mock_runtime(storage_ok=True, executor_ok=False)
        health = runtime.health_check()
        assert health["status"] == "degraded"
        assert health["executor"]["ok"] is False
    def _create_mock_runtime(
        self, storage_ok: bool = True, executor_ok: bool = True
    ) -> MagicMock:
        """Create a mock runtime with configurable health."""
        runtime = MagicMock()
        storage_error = None if storage_ok else "Storage connection failed"
        executor_error = None if executor_ok else "Executor unavailable"
        runtime.health_check.return_value = {
            "status": "ok" if (storage_ok and executor_ok) else "degraded",
            "storage": {"ok": storage_ok, "error": storage_error},
            "executor": {"ok": executor_ok, "error": executor_error},
            "last_error": storage_error or executor_error,
        }
        return runtime

class TestDescribeConfigSchema:
    """Tests for describe_config_schema contract tool."""
    def test_returns_settings_schema(self) -> None:
        """Test that settings schema is included."""
        runtime = self._create_mock_runtime()
        schema = runtime.describe_config_schema()
        assert "settings_schema" in schema
        assert isinstance(schema["settings_schema"], dict)
    def test_returns_workflow_definition_schema(self) -> None:
        """Test that workflow definition schema is included."""
        runtime = self._create_mock_runtime()
        schema = runtime.describe_config_schema()
        assert "workflow_definition_schema" in schema
        assert isinstance(schema["workflow_definition_schema"], dict)
    def _create_mock_runtime(self) -> MagicMock:
        """Create a mock runtime with schema response."""
        runtime = MagicMock()
        runtime.describe_config_schema.return_value = {
            "settings_schema": {
                "type": "object",
                "properties": {"storage": {"type": "object"}},
            },
            "workflow_definition_schema": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
            },
        }
        return runtime

def _write_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "workflows").mkdir()
    (cfg / "settings.yaml").write_text(
        yaml.safe_dump(
            {
                "service": {"name": "workflow-module"},
                "storage": {"backend": "sqlite", "sqlite": {"filename": "state.sqlite"}},
                "executor": {"backend": "local"},
                "authoring": {"enabled": False},
            },
            sort_keys=False,
        )
    )
    (cfg / "workflows" / "example.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "v1",
                "id": "example",
                "name": "Example Workflow",
                "version": 1,
                "steps": [
                    {"id": "start", "kind": "noop", "next": "wait"},
                    {"id": "wait", "kind": "wait_for_event", "event_type": "user.approved", "next": "done"},
                    {"id": "done", "kind": "noop"},
                ],
                "tags": ["demo"],
            },
            sort_keys=False,
        )
    )
    return cfg

class TestDashboardViews:
    @pytest.fixture
    def runtime(self, tmp_path: Path) -> WorkflowRuntime:
        return WorkflowRuntime.from_config_dir(_write_config(tmp_path))
    @pytest.fixture
    def mcp(self, runtime: WorkflowRuntime):
        return create_mcp_server(runtime)
    def test_dashboard_tools_registered(self, mcp) -> None:
        tool_names = [tool.name for tool in asyncio.run(mcp.list_tools())]
        assert "workflow_get_dashboard_summary" in tool_names
        assert "workflow_get_run_activity" in tool_names
        assert "workflow_get_run_graph_context" in tool_names
        assert "workflow_get_run_tasks" in tool_names
        assert "workflow_get_views" in tool_names
    @pytest.mark.asyncio
    async def test_dashboard_summary_and_views(self, mcp, runtime: WorkflowRuntime) -> None:
        published: list[dict[str, object]] = []
        def fake_invoker(tool_name: str, **kwargs):
            if tool_name == "events_publish":
                payload = kwargs.get("payload", {})
                published.append(
                    {
                        "event_id": f"evt-{len(published) + 1}",
                        "event_type": kwargs.get("event_type", ""),
                        "source": kwargs.get("source", ""),
                        "timestamp": "2026-05-06T00:00:00+00:00",
                        "payload": payload,
                        "metadata": kwargs.get("attributes", {}),
                    }
                )
                return {"event_id": f"evt-{len(published)}", "status": "published"}
            if tool_name == "events_query_history":
                entries = list(reversed(published))
                limit = int(kwargs.get("limit", len(entries)))
                return ToolResult(data=MagicMock(entries=entries[:limit]))
            if tool_name == "graph_graph_add_entity" or tool_name == "graph_graph_add_relationship":
                return {"ok": True}
            if tool_name == "graph_graph_get_entity":
                entity_id = str(kwargs.get("entity_id", ""))
                if entity_id.startswith("workflow-run-"):
                    run_id = entity_id.removeprefix("workflow-run-")
                    return ToolResult(data=EntityLookupData(
                        found=True, entity_id=entity_id,
                        entity=EntityData(
                            id=entity_id, type="WorkflowRun",
                            properties={"run_id": run_id, "workflow_id": "example", "status": "waiting"},
                        ),
                    ))
                return ToolResult(data=EntityLookupData(found=False, entity_id=entity_id))
            if tool_name == "graph_graph_get_neighbors":
                run_id = str(kwargs.get("entity_id", "")).removeprefix("workflow-run-")
                entity_id = str(kwargs.get("entity_id", ""))
                return ToolResult(data=NeighborsData(
                    entity_id=entity_id,
                    neighbors=[
                        EntityData(id="workflow-def-example", type="WorkflowDefinition", properties={"workflow_id": "example", "name": "Example Workflow"}),
                        EntityData(id=f"workflow-event-{run_id}-1", type="WorkflowEvent", properties={"run_id": run_id, "event_type": "workflow.step_transition", "status": "waiting"}),
                    ],
                    count=2,
                ))
            raise AssertionError(f"unexpected tool: {tool_name}")
        previous_invoker = get_service("tool_invoker")
        set_service("tool_invoker", fake_invoker)
        try:
            started = runtime.start_run(
                workflow_name_or_id="example",
                input={"env_id": "env-123", "target_app": "WebGoat"},
                envelope=parse_envelope({"run_id": "run-123", "tenant_id": "tenant-a"}),
            )
            runtime.emit_event(
                run_id="run-123",
                event_type="user.approved",
                payload={"approved": True},
                envelope=parse_envelope({"run_id": "run-123", "tenant_id": "tenant-a"}),
            )
            runtime.step_run(run_id="run-123", envelope=parse_envelope({"tenant_id": "tenant-a"}))
            summary_tool = await mcp.get_tool("workflow_get_dashboard_summary")
            activity_tool = await mcp.get_tool("workflow_get_run_activity")
            graph_tool = await mcp.get_tool("workflow_get_run_graph_context")
            tasks_tool = await mcp.get_tool("workflow_get_run_tasks")
            views_tool = await mcp.get_tool("workflow_get_views")
            summary_result = summary_tool.fn()
            activity_result = activity_tool.fn(run_id="run-123", limit=10)
            graph_context_result = graph_tool.fn(run_id="run-123", limit=10)
            run_tasks_result = tasks_tool.fn(run_id="run-123", limit=10)
            views_result = views_tool.fn()
            assert all(result.ok and result.data is not None for result in (
                summary_result, activity_result, graph_context_result,
                run_tasks_result, views_result,
            ))
            summary = summary_result.data
            activity = activity_result.data
            graph_context = graph_context_result.data
            run_tasks = run_tasks_result.data
            views = views_result.data.views
            assert started["run_id"] == "run-123"
            assert summary.overview["runs"] >= 1
            assert summary.overview["definitions"] >= 1
            assert summary.overview["activity"] >= 1
            assert summary.overview["graph_entities"] >= 1
            run_row = next(item for item in summary.runs if item["run_id"] == "run-123")
            assert run_row["workflow_name"] == "Example Workflow"
            assert run_row["activity_count"] >= 1
            assert any(item["event_type"] == "workflow.run_started" for item in summary.recent_activity)
            assert any(item["entity_type"] == "WorkflowDefinition" for item in summary.related_graph_entities)
            assert activity.count >= 1
            assert any(item["run_id"] == "run-123" for item in activity.entries)
            assert graph_context.count >= 1
            assert any(item["entity_type"] == "WorkflowDefinition" for item in graph_context.entries)
            assert isinstance(run_tasks.entries, list)
            component_ids = [component["id"] for component in views[0]["components"]]
            assert "workflow-status-mix" in component_ids
            assert "workflow-start-form" in component_ids
            assert "workflow-runs" in component_ids
            assert "workflow-tasks" in component_ids
            assert "workflow-activity-stream" in component_ids
            assert "workflow-graph-context" in component_ids
            assert "workflow-actions" in component_ids
        finally:
            set_service("tool_invoker", previous_invoker)

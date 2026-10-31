"""Bounded Workflow → Agent → LangGraph-adapter MCP lineage harness."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from factory.agent.interface import launch_managed_graph
from factory.agent.runtime.graph_contracts import GraphConfig
from factory.agent.runtime.runtime_contracts import RuntimeResult
from factory.agent.server import create_mcp_server as create_agent_server
from factory.graph.runtime.runtime import GraphRuntime
from factory.graph.server import create_mcp_server as create_graph_server
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils import registry as service_registry
from factory.mcp_utils.interface import get_envelope
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.execution.adapters import create_executor
from factory.workflow.runtime.models import Settings
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage
from factory.workflow.runtime.task_invoker_service import ServiceToolInvoker
from factory.workflow.server import create_mcp_server as create_workflow_server

from .managed_lineage_graph_setup import create_probe_server, install_graph_sink
from .managed_lineage_provider import create_fake_provider


class _FakeAgentAdapter:
    capability_scope_digest = "a" * 64


class _FakeLangGraphAdapter:
    """Current adapter-port fake that executes one MCP capability call."""

    def __init__(self, aggregator: MCPAggregator) -> None:
        self._invoke = NativeEnvelopeInvoker(aggregator).for_caller("agent")
        self.closed = False

    async def invoke_graph(self, request: Any) -> RuntimeResult:
        label = request.invocation.prompt
        response = await asyncio.to_thread(
            self._invoke,
            {"brick_name": "probe", "tool_name": "probe_record"},
            arguments={"label": label},
            idempotency_key=f"probe:{request.invocation.invocation_id}",
            envelope=dict(get_envelope() or {}),
        )
        if response.get("ok") is not True:
            return RuntimeResult(request.invocation.invocation_id, "", "failed")
        return RuntimeResult(
            request.invocation.invocation_id, "done", "completed",
            {"probe_label": label},
        )

    async def close(self) -> None:
        self.closed = True


class LineageHarness:
    def __init__(self, root: Path, monkeypatch: Any) -> None:
        self.root = root
        self.observed: dict[str, dict[str, Any]] = {}
        self.fake_bindings: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        graph_runtime = GraphRuntime({"default_backend": "networkx"})
        graph_runtime.get_graph("networkx").health_check()
        self.graph_server = create_graph_server(graph_runtime)
        self.probe_server = create_probe_server(self.observed, self._lock)
        self.fake_server = create_fake_provider(self.fake_bindings)
        self.agent_server = create_agent_server(SimpleNamespace(
            settings={}, swarm_registry=None, agent_registry=None,
            graph_registry=None, tool_registry=None, workflows={},
            get_capabilities=lambda: {}, health_check=lambda: {},
        ))
        self.aggregator = MCPAggregator(ToolCatalog("managed-lineage-root"))
        self.aggregator.set_available_bricks(
            ["agent", "graph", "probe", "qa_fake", "workflow"])
        self.aggregator._lazy._cache.update({
            "agent": self.agent_server, "graph": self.graph_server,
            "probe": self.probe_server, "qa_fake": self.fake_server,
        })
        self.workflow_runtime = self.workflow()
        self.aggregator._lazy._cache["workflow"] = create_workflow_server(
            self.workflow_runtime)
        native = NativeEnvelopeInvoker(self.aggregator)
        monkeypatch.setitem(
            service_registry._services, "tool_invoker_for_caller", native.for_caller,
        )
        from factory.mcp_server.runtime import graph_sink
        monkeypatch.setitem(
            service_registry._services, "tool_invocation_sink", graph_sink.materialize,
        )
        monkeypatch.setattr(
            "factory.mcp_server.interface.get_aggregator", lambda: self.aggregator,
        )
        monkeypatch.setattr(
            "factory.agent.runtime.adapters.create_runtime_pair",
            lambda: (_FakeAgentAdapter(), _FakeLangGraphAdapter(self.aggregator)),
        )
        install_graph_sink(self.graph_server, monkeypatch)

    def workflow(self, engine_id: str = "langgraph") -> WorkflowRuntime:
        folder = "workflow" if engine_id == "langgraph" else "fake-workflow"
        config = self.root / folder
        config.mkdir(exist_ok=True)
        storage = SqliteWorkflowStorage(config / "state.db")
        storage.init_schema()
        engines = [self._engine("langgraph", "agent"), self._engine("fake_compute", "qa_fake")]
        settings = Settings.model_validate({"execution_engines": {
            "engines": [item for item in engines if item["engine_id"] == engine_id],
        }})
        invoker = ServiceToolInvoker(
            NativeEnvelopeInvoker(self.aggregator).for_caller("workflow")
        )
        return WorkflowRuntime(
            config_dir=config, settings=settings,
            settings_raw=settings.model_dump(), workflows=[], storage=storage,
            executor=create_executor(), tool_invoker=invoker,
        )

    @staticmethod
    def _engine(engine_id: str, brick: str) -> dict[str, Any]:
        stem = "langgraph" if engine_id == "langgraph" else "fake_compute"
        return {
            "engine_id": engine_id,
            "invoke_target": {"brick_name": brick, "tool_name": f"execute_{stem}_attempt"},
            "cancel_target": {"brick_name": brick, "tool_name": f"cancel_{stem}_attempt"},
            "outcome": {
                "success": {"pointer": "/status", "equals": "completed"},
                "retryable": {"pointer": "/retryable", "equals": True},
                "error_pointer": "/error",
            },
        }

    def run(self, label: str) -> dict[str, Any]:
        definition = {
            "id": "managed-native", "name": "Managed Native",
            "resumable": True, "tool_allowlist": ["probe_record"],
            "nodes": [{
                "id": "specialist", "type": "agent", "model": "test",
                "system_prompt": "Call probe_record once.",
            }],
            "edges": [], "entry_points": ["specialist"],
        }
        envelope = Envelope(
            tenant_id="tenant", principal_id="principal",
            session_id=f"session-{label}", agent_id="orchestrator",
        )
        result = asyncio.run(launch_managed_graph(
            GraphConfig.model_validate(definition), label, {"label": label},
            run_key=f"{self.root.name}-lineage-{label}", origin_kind="dynamic",
            invocation_state={"label": label}, envelope=envelope.model_dump(mode="json"),
        ))
        return result.model_dump(mode="json")

    def run_fake(self) -> dict[str, Any]:
        return self.workflow("fake_compute").enroll_execution(
            engine_id="fake_compute",
            request={"inline": {"provider": "fake"}, "reference": None},
            provider_request_digest="f" * 64, run_key=f"{self.root.name}-fake",
            envelope=Envelope(tenant_id="tenant", principal_id="principal"),
        )

    def invocations(self, run_id: str) -> list[dict[str, Any]]:
        tool = asyncio.run(self.graph_server.get_tool("graph_get_tool_invocations_for_run"))
        result = tool.fn(run_id=run_id)
        assert result.ok and result.data is not None
        return [row for row in result.data.rows if row["brick_name"] == "probe"]

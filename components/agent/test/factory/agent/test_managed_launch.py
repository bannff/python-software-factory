"""Shared managed-launch facade contracts."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from factory.agent.runtime import managed_launch as module
from factory.agent.runtime.execution_manifest import DefinitionArtifact, DefinitionDescriptor


@pytest.fixture
def prepared(monkeypatch):
    manifest = SimpleNamespace(digest=SimpleNamespace(value="a" * 64))
    descriptor = DefinitionDescriptor(inline=DefinitionArtifact(
        schema_name="agent-execution-manifest", schema_version="1",
        identity="graph", version="a" * 64, content={"sealed": True},
    ))
    captured = {}
    monkeypatch.setattr(module, "prepare_execution_manifest", lambda *a, **kw: manifest)

    async def store(value, port):
        captured["manifest"] = value
        captured["dataset_port"] = port
        return descriptor

    monkeypatch.setattr(module, "store_manifest", store)
    return captured


def _success(run_key="run-key"):
    return {
        "ok": True,
        "result": {
            "kind": "tool",
            "structured_content": {
                "schema_version": "v1", "ok": True, "error": None,
                "idempotency_key": None,
                "data": {
                    "run_id": "workflow-run", "run_key": run_key,
                    "status": "running", "attempt_id": "attempt-1",
                    "attempt_revision": 1, "manifest_digest": "a" * 64,
                    "engine_id": "langgraph", "registration_digest": "b" * 64,
                    "request_digest": "c" * 64, "provider_request_digest": "a" * 64,
                    "execution_mode": "managed", "started_at": "now",
                    "result": None, "error": None,
                },
            },
        },
    }


@pytest.mark.asyncio
async def test_facade_binds_agent_and_invokes_exact_enrollment(monkeypatch, prepared):
    calls = []

    def invoke(target, **kwargs):
        calls.append((target, kwargs))
        return _success()

    monkeypatch.setattr(module, "get_service", lambda name: lambda caller: (
        invoke if name == "tool_invoker_for_caller" and caller == "agent" else None
    ))
    result = await module.launch_managed_graph(
        object(), "task", {"domain": "probe"}, run_key="run-key",
        origin_kind="dynamic", envelope={"session_id": "session"},
    )
    assert result.run_id == "workflow-run"
    assert prepared["manifest"].digest.value == "a" * 64
    assert calls[0][0] == {
        "brick_name": "workflow", "tool_name": "enroll_execution",
    }
    kwargs = calls[0][1]
    assert kwargs["enrollment"] == {
        "run_key": "run-key", "manifest_digest": "a" * 64,
    }
    assert kwargs["idempotency_key"] == "run-key"
    assert kwargs["arguments"]["run_key"] == "run-key"
    assert kwargs["arguments"]["provider_request_digest"] == "a" * 64


@pytest.mark.asyncio
@pytest.mark.parametrize("response, message", [
    ({"ok": False, "error": {"type": "denied"}}, "transport failure"),
    ({"ok": True, "result": {}}, "malformed native transport"),
    ({"ok": True, "result": {"kind": "tool", "structured_content": {}}},
     "malformed ToolResult"),
    ({"ok": True, "result": {"kind": "tool", "structured_content": {
        "schema_version": "v1", "ok": False, "error": {"message": "boom"},
    }}}, "failed"),
])
async def test_facade_fails_loudly_on_every_transport_layer(
    monkeypatch, prepared, response, message,
):
    monkeypatch.setattr(
        module, "get_service", lambda name: lambda caller: (
            lambda target, **kwargs: response
        ),
    )
    with pytest.raises(RuntimeError, match=message):
        await module.launch_managed_graph(
            object(), "task", {}, run_key="run-key", origin_kind="registered",
        )


@pytest.mark.asyncio
async def test_facade_requires_caller_bound_service(monkeypatch):
    monkeypatch.setattr(module, "get_service", lambda name: None)
    with pytest.raises(RuntimeError, match="tool_invoker_for_caller"):
        await module.launch_managed_graph(
            object(), "task", {}, run_key="run-key", origin_kind="registered",
        )


def test_execution_manifest_materializes_immutable_registered_graph() -> None:
    from factory.agent.registry.defaults_code_scan import SAST_SCAN_GRAPH
    from factory.agent.runtime.execution_manifest.prepare import prepare_execution_manifest

    context = {
        "vuln_class": "idor", "target_app": "app", "run_id": "requested",
        "target_packages": "pkg", "sast_workspace": "/tmp/workspace",
    }
    manifest = prepare_execution_manifest(SAST_SCAN_GRAPH, "scan", context)
    assert len(manifest.nodes) == 6
    assert manifest.entry_points == ("gptoss-sast", "sonnet-sast", "glm5-sast")
    assert manifest.graph_id == SAST_SCAN_GRAPH.id
    assert manifest.digest is not None

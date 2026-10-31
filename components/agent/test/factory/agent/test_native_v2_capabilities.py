"""Agent seam tests for the native public-MCP-v2 capability client."""
from __future__ import annotations


def test_agent_binds_exact_scope_without_a_framework_client(monkeypatch) -> None:
    from factory.agent.runtime.adapters import native_v2_capabilities as module

    captured = {}
    sentinel = object()

    def fake_client(server, scope):
        captured["server"] = server
        captured["scope"] = scope
        return sentinel

    monkeypatch.setattr(module, "NativeV2ScopedCapabilityClient", fake_client)
    from factory.mcp_utils.interface import CapabilityScope

    server = object()
    scope = CapabilityScope.create(
        "graph-run", {"graph_get_entity", "memory_retrieve"},
    )
    client = module.create_native_v2_capability_client(server, scope)

    assert client is sentinel
    assert captured["server"] is server
    assert captured["scope"].policy_id == "graph-run"
    assert captured["scope"].tool_names == frozenset({
        "graph_get_entity", "memory_retrieve",
    })

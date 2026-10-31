"""Focused tests for registered graph contracts, scoping, fan-in, and defaults."""
from __future__ import annotations

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")


def test_contract_facade_reexports_identical_classes() -> None:
    from factory.agent.runtime import graph_contracts
    from factory.agent.runtime.registry_contracts import AgentNodeRef, GraphConfig
    assert AgentNodeRef is graph_contracts.AgentNodeRef
    assert GraphConfig is graph_contracts.GraphConfig


def test_node_over_persona_precedence_and_explicit_empty(monkeypatch) -> None:
    from factory.agent.runtime.agent_contracts import AgentConfig
    from factory.agent.runtime.execution_manifest.prepare import prepare_execution_manifest
    from factory.agent.runtime.graph_contracts import GraphConfig

    persona = AgentConfig(
        id="researcher", name="Researcher", model="persona-model",
        system_prompt="persona", tools=["think"], skills=["base"],
        context={"shared": "base", "base": True},
    )
    monkeypatch.setattr(
        "factory.agent.registry.unified.unified_personas", lambda: [persona],
    )
    graph = GraphConfig.model_validate({
        "id": "precedence", "name": "Precedence", "nodes": [{
            "id": "quality", "type": "agent", "agent_id": "researcher",
            "model": "node-model", "system_prompt": "node",
            "tools": [], "skills": [], "context": {"shared": "node"},
            "mcp_tool_allowlist": [], "read_only": True,
        }], "entry_point": "quality",
    })
    resolved = prepare_execution_manifest(graph, "task", {}).nodes[0]
    assert resolved.model.model_id == "node-model"
    assert resolved.system_prompt == "node"
    assert resolved.tools.local == () and resolved.skills.names == ()
    assert resolved.initial_state == {"shared": "node", "base": True}


def test_read_only_allowlist_fails_closed() -> None:
    from factory.agent.runtime.graph_contracts import AgentNodeRef
    with pytest.raises(ValueError, match="mutating"):
        AgentNodeRef(
            id="bad", type="agent", read_only=True,
            mcp_tool_allowlist=["dataset_submit_generation"],
        )


def test_dataset_research_registration_is_fixed_scoped_fanin() -> None:
    from factory.agent.registry.defaults import AGENTS_TYPED, GRAPHS_TYPED
    assert any(agent.id == "dataset-researcher" for agent in AGENTS_TYPED)
    graph = next(item for item in GRAPHS_TYPED if item.id == "dataset-research")
    assert len(graph.nodes) == 6 and len(graph.edges) == 8
    assert graph.entry_points == ["planner"] and graph.terminal_node == "drafter"
    assert {node.agent_id for node in graph.nodes} == {"dataset-researcher"}
    research_edges = [edge for edge in graph.edges if edge.target == "drafter"]
    assert len(research_edges) == 4
    assert {edge.condition for edge in research_edges} == {"all-predecessors-valid"}
    for node in graph.nodes:
        assert node.read_only and node.mcp_tool_allowlist is not None
        assert not any("submit" in tool or "publish" in tool
                       for tool in node.mcp_tool_allowlist)


def test_registered_node_manifest_uses_exact_tools_and_schema(monkeypatch) -> None:
    from factory.agent.runtime.agent_contracts import AgentConfig
    from factory.agent.runtime.execution_manifest.prepare import prepare_execution_manifest
    from factory.agent.runtime.graph_contracts import GraphConfig

    persona = AgentConfig(
        id="researcher", name="Researcher", model="m",
        system_prompt="base", tools=["think"], skills=[],
        exact_tools=True,
    )
    monkeypatch.setattr(
        "factory.agent.registry.unified.unified_personas", lambda: [persona],
    )
    graph = GraphConfig.model_validate({
        "id": "scoped", "name": "Scoped", "nodes": [{
            "id": "source", "type": "agent", "agent_id": "researcher",
            "read_only": True,
            "mcp_tool_allowlist": ["dataset_get_artifact"],
            "output_schema": "research-evidence-v1",
        }], "entry_point": "source",
    })
    node = prepare_execution_manifest(graph, "task", {}).nodes[0]
    assert node.tools.resolved_mcp_allowlist == ("dataset_get_artifact",)
    assert node.tools.exact_tools is True
    assert node.output_schema is not None
    assert node.output_schema.name == "research-evidence-v1"


def test_read_only_allowlist_rejects_prefix_spoof() -> None:
    from factory.agent.runtime.graph_contracts import AgentNodeRef
    with pytest.raises(ValueError, match="mutating"):
        AgentNodeRef(
            id="bad", type="agent", read_only=True,
            mcp_tool_allowlist=["evil_get_secrets"],
        )


@pytest.mark.parametrize("override", [
    {"edges": [{"source": "missing", "target": "a"}]},
    {"entry_points": ["missing"]},
    {"terminal_node": "missing"},
    {"nodes": [
        {"id": "a", "type": "agent"}, {"id": "a", "type": "agent"},
    ]},
])
def test_graph_topology_is_validated_eagerly(override) -> None:
    from factory.agent.runtime.graph_contracts import GraphConfig
    raw = {
        "id": "invalid", "name": "Invalid",
        "nodes": [{"id": "a", "type": "agent"}], **override,
    }
    with pytest.raises(ValueError):
        GraphConfig.model_validate(raw)

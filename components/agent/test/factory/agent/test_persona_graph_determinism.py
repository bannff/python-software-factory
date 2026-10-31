from __future__ import annotations

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from hypothesis import given, strategies as st

from factory.agent.registry.defaults import AGENTS_TYPED
from factory.agent.runtime.background.persona_graph import persona_graph
from factory.agent.runtime.execution_manifest.prepare import prepare_execution_manifest


class Registry:
    def get(self, agent_id: str):
        return next((item for item in AGENTS_TYPED if item.id == agent_id), None)


@given(st.sampled_from([item.id for item in AGENTS_TYPED]))
def test_persona_graph_and_manifest_are_deterministic(agent_id: str) -> None:
    first = persona_graph(Registry(), agent_id)
    second = persona_graph(Registry(), agent_id)
    assert first == second
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.nodes[0].id == first.nodes[0].agent_id == agent_id


def test_default_persona_manifest_digest_is_reproducible() -> None:
    graph = persona_graph(Registry(), "companion-x-default")
    one = prepare_execution_manifest(
        graph, "bounded task", {"origin_session_id": "session-1"},
    )
    two = prepare_execution_manifest(
        graph, "bounded task", {"origin_session_id": "session-1"},
    )
    assert one.digest == two.digest


def test_unknown_persona_is_rejected_before_manifest_creation() -> None:
    try:
        persona_graph(Registry(), "missing-persona")
    except ValueError as exc:
        assert str(exc) == "unknown_agent_id"
    else:
        raise AssertionError("unknown persona accepted")


_STANDALONE = [item.id for item in AGENTS_TYPED if "{{" not in item.system_prompt]


@given(st.sampled_from(_STANDALONE))
def test_every_builtin_persona_compiles_as_a_background_cycle(agent_id: str) -> None:
    """M7.6 live defect: Developer's ``devtools_*`` MCP tools failed as unknown
    local built-ins inside ``launch_background`` → ``spawn_background`` errored
    on every Scheduler fire. Persona tools must partition into local + MCP."""
    graph = persona_graph(Registry(), agent_id, "loop-cycle-report-v1")
    manifest = prepare_execution_manifest(
        graph, "cycle", {"origin_session_id": "s", "origin_thread_id": "t"},
        invocation_state={"kind": "workflow_loop_cycle"}, origin_kind="dynamic",
    )
    assert manifest.digest is not None
    assert manifest.nodes[0].output_schema is not None


def test_developer_persona_freezes_devtools_as_explicit_mcp_scope() -> None:
    from factory.agent.runtime.execution_manifest.preparation_support import partition_tools

    persona = Registry().get("developer")
    local, mcp = partition_tools(list(persona.tools))
    assert persona.exact_tools is True and mcp and "devtools_read_file" in mcp
    manifest = prepare_execution_manifest(
        persona_graph(Registry(), "developer", "loop-cycle-report-v1"), "cycle", {},
    )
    tools = manifest.nodes[0].tools
    assert tools.mcp_mode == "explicit"
    assert tools.exact_tools is True
    assert tools.resolved_mcp_allowlist == tuple(mcp)
    assert tuple(tool.name for tool in tools.local) == tuple(local)

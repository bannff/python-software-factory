from __future__ import annotations

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from copy import deepcopy

from hypothesis import given, strategies as st

from factory.agent.registry.defaults import GRAPHS_TYPED
from factory.agent.runtime.execution_manifest.canonical import canonical_bytes
from factory.agent.runtime.execution_manifest.prepare import (
    REGISTERED_GRAPH_IDS, prepare_execution_manifest,
    prepare_registered_execution_manifest,
)
from factory.agent.runtime.graph_contracts import GraphConfig

CONTEXT = {
    "run_id": "r1", "target_app": "app", "vuln_class": "idor",
    "target_packages": ["pkg"], "sast_workspace": "/tmp/ws",
    "target_url": "http://target", "sandbox_env_id": "env",
    "sast_run_id": "s1", "agent_id": "agent", "metric_prefix": "metric",
    "eval_task_description": "evaluate", "eval_evaluators": ["goal_success"],
    "eval_rubric": "rubric", "dataset_ref": "dataset", "objective": "research",
    "output_format": "json", "account_id": "123", "region": "us-east-1",
}


def test_exact_registered_matrix_compiles_without_recursive_refs() -> None:
    assert len(REGISTERED_GRAPH_IDS) == 17
    for graph_id in REGISTERED_GRAPH_IDS:
        manifest = prepare_registered_execution_manifest(graph_id, "task", CONTEXT)
        assert manifest.digest is not None
        assert all(node.type in {"agent", "swarm"} for node in manifest.nodes)
        assert manifest.entry_points


def test_registered_and_dynamic_differ_only_in_origin_and_digest() -> None:
    config = next(item for item in GRAPHS_TYPED if item.id == "rt-sast-sonnet")
    registered = prepare_registered_execution_manifest(config.id, "task", CONTEXT)
    dynamic = prepare_execution_manifest(config, "task", CONTEXT)
    left = registered.model_dump(mode="json", exclude={"origin", "digest"})
    right = dynamic.model_dump(mode="json", exclude={"origin", "digest"})
    assert left == right
    assert registered.origin.kind == "registered"
    assert dynamic.origin.kind == "dynamic"


def test_tool_tri_state_is_frozen_without_erasing_local_tools() -> None:
    agent = {"type": "agent", "model": "model", "system_prompt": "x",
             "tools": ["think"]}
    config = GraphConfig.model_validate({
        "id": "tools", "name": "Tools", "tool_allowlist": ["graph_get_entity"],
        "nodes": [
            {**agent, "id": "inherit"},
            {**agent, "id": "empty", "mcp_tool_allowlist": []},
            {**agent, "id": "scoped", "mcp_tool_allowlist": ["memory_retrieve"]},
        ], "entry_points": ["inherit", "empty", "scoped"],
    })
    nodes = prepare_execution_manifest(config, "task", {}).nodes
    expected = [
        ("inherit", ("graph_get_entity",)),
        ("empty", ()),
        ("explicit", ("memory_retrieve",)),
    ]
    for node, (mode, resolved) in zip(nodes, expected, strict=True):
        assert node.tools.mcp_mode == mode
        assert node.tools.resolved_mcp_allowlist == resolved
        assert tuple(tool.name for tool in node.tools.local) == ("think",)


def test_absent_graph_scope_resolves_fail_closed_empty() -> None:
    config = GraphConfig.model_validate({
        "id": "closed", "name": "Closed", "nodes": [{
            "id": "a", "type": "agent", "model": "model",
            "system_prompt": "x", "tools": [],
        }], "entry_point": "a",
    })
    tools = prepare_execution_manifest(config, "task", {}).nodes[0].tools
    assert tools.mcp_mode == "inherit"
    assert tools.resolved_mcp_allowlist == ()


@given(st.dictionaries(st.text(min_size=1), st.integers(), max_size=20))
def test_canonical_json_is_independent_of_mapping_order(value: dict[str, int]) -> None:
    reversed_value = dict(reversed(list(deepcopy(value).items())))
    assert canonical_bytes(value) == canonical_bytes(reversed_value)

from __future__ import annotations

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")
from hypothesis import given, strategies as st

from factory.agent.registry.defaults import GRAPHS_TYPED
from factory.agent.registry.defaults_dev_review import REVIEW_DEVTOOLS
from factory.agent.runtime.execution_manifest.prepare import (
    prepare_registered_execution_manifest,
)
from factory.agent.runtime.graph_contracts import AgentNodeRef
from factory.evals.interface import get_review_policy


def test_review_graphs_are_discoverable_personalless_and_sealed() -> None:
    graphs = {graph.id: graph for graph in GRAPHS_TYPED}
    assert {"review-qa", "review-meta"} <= set(graphs)
    for policy_id in ("review-qa", "review-meta"):
        policy = get_review_policy(policy_id)
        graph = graphs[policy_id]
        node = graph.nodes[0]
        assert node.agent_id is None and node.read_only is True
        assert tuple(node.mcp_tool_allowlist or ()) == REVIEW_DEVTOOLS
        assert node.system_prompt == policy.rubric
        manifest = prepare_registered_execution_manifest(
            policy_id, "review supplied evidence", {},
        )
        frozen = manifest.nodes[0]
        assert manifest.origin.kind == "registered"
        assert manifest.digest is not None
        assert frozen.tools.mcp_mode == "explicit"
        assert frozen.tools.exact_tools is True
        assert frozen.tools.resolved_mcp_allowlist == REVIEW_DEVTOOLS


@given(st.sampled_from([
    "devtools_write_file", "devtools_edit_file", "devtools_run_command",
    "devtools_cancel_command", "devtools_git_stage", "devtools_git_commit",
    "devtools_git_push", "unknown_tool",
]))
def test_read_only_reviewer_structurally_rejects_mutating_tools(tool: str) -> None:
    with pytest.raises(ValueError, match="mutating/unknown"):
        AgentNodeRef(
            id="review", type="agent", agent_id=None, model="model",
            system_prompt="rubric", read_only=True,
            mcp_tool_allowlist=[*REVIEW_DEVTOOLS, tool],
        )

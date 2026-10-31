"""Behavior tests for compile_spec mapper (Phase 1 swarm canary)."""
from __future__ import annotations

import pytest

from factory.agent.executors.compile_spec import compile_spec
from factory.agent.runtime.coordination import swarm_request
from factory.agent.runtime.registry_contracts import (
    SuccessRubric,
    SwarmConfig,
    WorkflowAgentRef,
    WorkflowSpec,
)


@pytest.fixture
def rubric() -> SuccessRubric:
    return SuccessRubric(
        output_entity_type="finding",
        match_on=("cve_id", "file_path"),
        ground_truth_ref="gt://test-v1",
    )


@pytest.fixture
def swarm_spec(rubric: SuccessRubric) -> WorkflowSpec:
    return WorkflowSpec(
        id="test-swarm",
        kind="swarm",
        agents=[
            WorkflowAgentRef(
                role="scanner",
                skill_id="idor-scan",
                model_id="us.amazon.nova-lite-v1:0",
                tools=["http_request", "code_exec"],
            ),
            WorkflowAgentRef(
                role="verifier",
                skill_id="verify-finding",
                model_id="us.amazon.nova-pro-v1:0",
                tools=[],
            ),
        ],
        success_rubric=rubric,
        metadata={"vuln_class": "idor", "target_app": "webgoat"},
        context_vars={"target": "app-1"},
    )


# --- 1. Swarm mapping correctness ---

def test_compile_swarm_maps_agents_correctly(swarm_spec: WorkflowSpec) -> None:
    result = compile_spec(swarm_spec)

    assert isinstance(result, SwarmConfig)
    assert result.id == "test-swarm"
    assert result.kind == "swarm"
    assert len(result.agents) == 2

    scanner = result.agents[0]
    assert scanner.id == "scanner"
    assert scanner.model == "us.amazon.nova-lite-v1:0"
    assert scanner.system_prompt == "scanner"
    assert scanner.skills == ["idor-scan"]
    assert scanner.tools == ["http_request", "code_exec"]

    verifier = result.agents[1]
    assert verifier.id == "verifier"
    assert verifier.model == "us.amazon.nova-pro-v1:0"
    assert verifier.skills == ["verify-finding"]
    assert verifier.tools == []


def test_compile_swarm_entry_point_is_first_agent(swarm_spec: WorkflowSpec) -> None:
    result = compile_spec(swarm_spec)
    assert result.entry_point == "scanner"


def test_compile_swarm_context_vars_become_keys(swarm_spec: WorkflowSpec) -> None:
    result = compile_spec(swarm_spec)
    assert result.context_vars == ["target"]


# --- 2. Current LangGraph coordination accepts the compiled config ---

def test_compiled_config_translates_to_bounded_graph_request(
    swarm_spec: WorkflowSpec,
) -> None:
    config = compile_spec(swarm_spec)
    request = swarm_request(config, "scan", {"run_id": "run-1"}, "scope")
    assert [node.node_id for node in request.nodes] == ["scanner", "verifier"]
    assert [(edge.source, edge.target) for edge in request.edges] == [
        ("scanner", "verifier"),
    ]
    assert request.invocation.capability_scope_digest == "scope"


# --- 3. Unsupported kinds raise NotImplementedError ---

def test_graph_kind_raises_not_implemented(rubric: SuccessRubric) -> None:
    spec = WorkflowSpec(id="g-1", kind="graph", success_rubric=rubric)
    with pytest.raises(NotImplementedError, match="graph not yet supported"):
        compile_spec(spec)


def test_workflow_kind_raises_not_implemented(rubric: SuccessRubric) -> None:
    spec = WorkflowSpec(id="w-1", kind="workflow", success_rubric=rubric)
    with pytest.raises(NotImplementedError, match="workflow not yet supported"):
        compile_spec(spec)


# --- 4. Domain fields in metadata do NOT leak to SwarmConfig ---

def test_metadata_vuln_class_does_not_leak_to_swarm_config(swarm_spec: WorkflowSpec) -> None:
    result = compile_spec(swarm_spec)
    dumped = result.model_dump()
    assert "vuln_class" not in dumped
    assert "target_app" not in dumped

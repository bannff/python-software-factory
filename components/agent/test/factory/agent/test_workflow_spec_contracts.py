"""Behavior tests for WorkflowSpec contract (bd python-factory-tirq, slice 0).

Each test verifies one contract clause. Names state the requirement.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from factory.agent.runtime.registry_contracts import (
    EdgeConfig,
    SuccessRubric,
    WorkflowAgentRef,
    WorkflowSpec,
)


# --- Fixtures ---

@pytest.fixture
def rubric() -> SuccessRubric:
    return SuccessRubric(
        output_entity_type="finding",
        match_on=("cve_id", "file_path"),
        ground_truth_ref="gt://idor-webgoat-v1",
    )


@pytest.fixture
def minimal_spec(rubric: SuccessRubric) -> dict:
    return {"id": "spec-1", "kind": "swarm", "success_rubric": rubric.model_dump()}


# --- 1. Valid construction and round-trip ---

def test_valid_spec_round_trips_through_model_dump(rubric: SuccessRubric) -> None:
    spec = WorkflowSpec(id="wf-abc", kind="graph", success_rubric=rubric)
    assert WorkflowSpec.model_validate(spec.model_dump()) == spec


def test_valid_spec_with_all_optional_fields(rubric: SuccessRubric) -> None:
    agent = WorkflowAgentRef(role="scanner", skill_id="idor-scan", model_id="claude-4")
    edge = EdgeConfig(source="a", target="b", condition="found > 0")
    spec = WorkflowSpec(
        id="full-spec",
        kind="workflow",
        agents=[agent],
        edges=[edge],
        success_rubric=rubric,
        gt_path="/data/gt.jsonl",
        metadata={"vuln_class": "idor"},
        context_vars={"target": "app-1"},
    )
    rebuilt = WorkflowSpec.model_validate(spec.model_dump())
    assert rebuilt == spec


# --- 2. extra="forbid" rejects unknown top-level fields ---

def test_extra_forbid_rejects_vuln_class_at_top_level(minimal_spec: dict) -> None:
    minimal_spec["vuln_class"] = "idor"
    with pytest.raises(ValidationError, match="vuln_class"):
        WorkflowSpec.model_validate(minimal_spec)


def test_extra_forbid_rejects_target_app_at_top_level(minimal_spec: dict) -> None:
    minimal_spec["target_app"] = "webgoat"
    with pytest.raises(ValidationError, match="target_app"):
        WorkflowSpec.model_validate(minimal_spec)


def test_vuln_class_succeeds_when_nested_in_metadata(minimal_spec: dict) -> None:
    minimal_spec["metadata"] = {"vuln_class": "idor", "target_app": "webgoat"}
    spec = WorkflowSpec.model_validate(minimal_spec)
    assert spec.metadata["vuln_class"] == "idor"
    assert spec.metadata["target_app"] == "webgoat"


# --- 3. success_rubric is required ---

def test_omitting_success_rubric_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="success_rubric"):
        WorkflowSpec.model_validate({"id": "x", "kind": "swarm"})


# --- 4. reward_formula defaults to "f1" ---

def test_reward_formula_defaults_to_f1() -> None:
    rubric = SuccessRubric(
        output_entity_type="vuln",
        match_on=("id",),
        ground_truth_ref="gt://ref",
    )
    assert rubric.reward_formula == "f1"


# --- 5. kind only accepts the three literals ---

@pytest.mark.parametrize("valid_kind", ["swarm", "graph", "workflow"])
def test_kind_accepts_valid_literals(valid_kind: str, rubric: SuccessRubric) -> None:
    spec = WorkflowSpec(id="k", kind=valid_kind, success_rubric=rubric)
    assert spec.kind == valid_kind


def test_kind_rejects_invalid_literal(minimal_spec: dict) -> None:
    minimal_spec["kind"] = "pipeline"
    with pytest.raises(ValidationError, match="kind"):
        WorkflowSpec.model_validate(minimal_spec)


# --- 6. edges accepts EdgeConfig instances ---

def test_edges_accepts_edge_config_instances(rubric: SuccessRubric) -> None:
    edges = [EdgeConfig(source="scan", target="verify")]
    spec = WorkflowSpec(id="e", kind="graph", edges=edges, success_rubric=rubric)
    assert spec.edges[0].source == "scan"
    assert spec.edges[0].target == "verify"


# --- 7. SuccessRubric requires its mandatory fields ---

def test_success_rubric_requires_output_entity_type() -> None:
    with pytest.raises(ValidationError, match="output_entity_type"):
        SuccessRubric(match_on=("x",), ground_truth_ref="gt://a")  # type: ignore[call-arg]


def test_success_rubric_requires_match_on() -> None:
    with pytest.raises(ValidationError, match="match_on"):
        SuccessRubric(output_entity_type="f", ground_truth_ref="gt://a")  # type: ignore[call-arg]


def test_success_rubric_requires_ground_truth_ref() -> None:
    with pytest.raises(ValidationError, match="ground_truth_ref"):
        SuccessRubric(output_entity_type="f", match_on=("x",))  # type: ignore[call-arg]

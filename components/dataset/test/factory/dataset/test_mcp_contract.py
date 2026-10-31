"""Whole-server strict ingress/egress regressions for Dataset MCP tools."""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from pydantic import ValidationError

from factory.dataset.mcp import can_terminal, deterministic
from factory.dataset.server import create_mcp_server
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.mcp_utils.interface import ToolResult


TOOLS = {
    "dataset_validate_blueprint", "dataset_materialize_blueprint",
    "dataset_publish_scenario_pack", "dataset_submit_generation", "dataset_get_job",
    "dataset_cancel_job", "dataset_get_scenario_pack", "dataset_get_artifact",
    "dataset_resolve_artifact", "dataset_materialize_can_training_bundle",
    "dataset_query_dbc_catalog", "dataset_resolve_dbc_candidate",
    "dataset_list_failure_patterns", "dataset_inspect_failure_pattern",
    "dataset_project_can_graph", "can_pipeline_overview",
    "dataset_publish_definition_artifact", "dataset_resolve_definition_artifact",
}


def _tool(mcp: ToolCatalog, name: str):
    return asyncio.run(mcp.get_tool(name)).fn


def test_every_dataset_tool_has_strict_local_dtos_and_exact_typed_egress(tmp_path: Path) -> None:
    server = create_mcp_server(tmp_path)
    observed = {_tool(server, name) for name in TOOLS}
    assert len(observed) == 18
    assert sum(getattr(tool, "_mcp_category") == "deterministic" for tool in observed) == 10
    assert sum(getattr(tool, "_mcp_category") == "operational" for tool in observed) == 8
    for tool in observed:
        input_model = tool._mcp_input_model
        output_model = tool._mcp_output_model
        assert input_model.__module__.startswith("factory.dataset.mcp.contracts")
        assert output_model.__module__.startswith("factory.dataset.mcp.contracts")
        assert input_model.model_config["extra"] == "forbid"
        assert input_model.model_config["strict"] is True
        annotation = inspect.signature(tool).return_annotation
        assert annotation == f"ToolResult[{output_model.__name__}]"


def test_unknown_ingress_is_rejected_before_dataset_runtime(tmp_path: Path) -> None:
    with pytest.raises(SchemaMigrationError):
        _tool(create_mcp_server(tmp_path), "dataset_query_dbc_catalog")({"unknown": True})


def test_optional_artifact_read_preserves_successful_null_payload(tmp_path: Path) -> None:
    mcp = ToolCatalog("dataset-contract")
    deterministic.register(mcp, tmp_path)
    result = _tool(mcp, "dataset_get_artifact")({"job_id": "missing"})
    assert result.ok is True
    assert result.data is None


def test_can_terminal_conflict_is_a_successful_typed_domain_outcome(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(can_terminal, "dataset_materialize_can_training_bundle", lambda *_: {
        "schema_version": "1.0", "status": "conflict", "attempt_id": "same",
        "request_sha256": "a" * 64, "existing_request_sha256": "b" * 64,
        "error": "attempt_id is already bound to a different request",
    })
    mcp = ToolCatalog("dataset-contract")
    can_terminal.register(mcp, tmp_path)
    result = _tool(mcp, "dataset_materialize_can_training_bundle")({
        "attempt_id": "same", "mf4_dir": "/captures",
    })
    assert result.ok is True
    assert result.data.status == "conflict"
    assert result.data.attempt_id == "same"


@pytest.mark.parametrize("name", sorted(TOOLS))
def test_every_dataset_tool_rejects_unknown_flat_ingress(
    tmp_path: Path, name: str,
) -> None:
    with pytest.raises((SchemaMigrationError, ValidationError)):
        _tool(create_mcp_server(tmp_path), name)({"unknown_argument": True})


@pytest.mark.parametrize("name", sorted(TOOLS))
def test_every_dataset_output_has_a_serialized_v1_tool_result_envelope(
    tmp_path: Path, name: str,
) -> None:
    output_model = _tool(create_mcp_server(tmp_path), name)._mcp_output_model
    payload = ToolResult(ok=True, data=output_model.model_construct()).model_dump(
        mode="json", exclude_computed_fields=True,
    )
    assert payload["schema_version"] == "v1"
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["idempotency_key"] is None
    assert isinstance(payload["data"], dict)


def test_optional_job_read_preserves_successful_null_payload(tmp_path: Path) -> None:
    from factory.dataset.mcp import operational
    mcp = ToolCatalog("dataset-contract")
    operational.register(mcp, tmp_path)
    result = _tool(mcp, "dataset_get_job")({"job_id": "missing"})
    assert result.ok is True
    assert result.data is None
    assert result.error is None


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_can_terminal_typed_domain_outcomes_are_successful_data(
    tmp_path: Path, monkeypatch, status: str,
) -> None:
    payload = {
        "schema_version": "1.0", "status": status, "attempt_id": "attempt",
        "request_sha256": "a" * 64,
    }
    if status == "completed":
        payload["training_bundle"] = {"prepared_by_can_id": {}}
    else:
        payload["error"] = "expected failure"
    monkeypatch.setattr(can_terminal, "dataset_materialize_can_training_bundle", lambda *_: payload)
    mcp = ToolCatalog("dataset-contract")
    can_terminal.register(mcp, tmp_path)
    result = _tool(mcp, "dataset_materialize_can_training_bundle")({
        "attempt_id": "attempt", "mf4_dir": "/captures",
    })
    assert result.ok is True
    assert result.data.status == status


def test_can_terminal_replay_and_strict_nested_scalar_rejection(
    tmp_path: Path, monkeypatch,
) -> None:
    completed = {
        "schema_version": "1.0", "status": "completed", "attempt_id": "same",
        "request_sha256": "a" * 64, "training_bundle": {"prepared_by_can_id": {}},
    }
    monkeypatch.setattr(can_terminal, "dataset_materialize_can_training_bundle", lambda *_: completed)
    mcp = ToolCatalog("dataset-contract")
    can_terminal.register(mcp, tmp_path)
    tool = _tool(mcp, "dataset_materialize_can_training_bundle")
    assert tool({"attempt_id": "same", "mf4_dir": "/captures"}).data.root == completed
    with pytest.raises(SchemaMigrationError):
        tool({
            "attempt_id": "strict", "mf4_dir": "/captures",
            "message_fingerprints": [{"arbitration_id": "1", "dlc": "8", "is_extended": "false"}],
        })

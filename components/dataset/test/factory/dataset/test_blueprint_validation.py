"""Fail-closed blueprint validation, MCP metadata, and architecture canaries."""
from __future__ import annotations

import ast
import asyncio
import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from factory.dataset.interface import dataset_validate_blueprint
from factory.dataset.runtime.blueprint_models import DatasetBlueprint
from factory.dataset.server import create_mcp_server

from .blueprint_fixtures import QUALITY_POLICY, blueprint, configure


def _mutated(value: DatasetBlueprint, field: str, replacement) -> DatasetBlueprint:
    data = value.model_dump(mode="json")
    data[field] = replacement
    return DatasetBlueprint.model_validate(data)


@pytest.mark.parametrize(
    ("field", "mutator", "message"),
    [
        ("recipe", lambda old: {**old, "id": "unknown"}, "recipe"),
        ("stages", lambda old: old + [{**old[0], "id": "unknown"}], "stage"),
        ("output_schema", lambda old: {**old, "digest": "0" * 64}, "schema"),
        ("source_evidence", lambda old: [{**old[0], "version": "2"}], "evidence"),
        ("capabilities", lambda old: [{**old[0], "id": "unknown"}], "capability"),
        ("quality_policy", lambda old: {**old, "digest": "0" * 64}, "policy"),
    ],
)
def test_unknown_or_mismatched_references_fail_closed(
    tmp_path: Path, monkeypatch, field: str, mutator, message: str,
) -> None:
    valid = blueprint(tmp_path / "store")
    candidate = _mutated(valid, field, mutator(valid.model_dump(mode="json")[field]))
    configure(monkeypatch, valid)
    with pytest.raises(ValueError, match=message):
        dataset_validate_blueprint(candidate, tmp_path / "store")


def test_stage_order_is_not_normalized_by_registry(tmp_path: Path, monkeypatch) -> None:
    valid = blueprint(tmp_path / "store")
    stage = valid.stages[0].model_copy(update={"id": "other"})
    configure(monkeypatch, valid)
    for stages in ((valid.stages[0], stage), (stage, valid.stages[0])):
        with pytest.raises(ValueError, match="order"):
            dataset_validate_blueprint(valid.model_copy(update={"stages": stages}), tmp_path / "store")


@pytest.mark.parametrize(
    "field",
    ["validator", "evaluator", "import", "callable", "script", "command", "promotion", "accept"],
)
def test_executable_and_decision_fields_cannot_be_supplied(tmp_path: Path, field: str) -> None:
    data = blueprint(tmp_path / "store").model_dump(mode="json")
    data[field] = "agent-controlled"
    with pytest.raises(ValidationError):
        DatasetBlueprint.model_validate(data)


def test_validate_is_write_free(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "store"
    value = blueprint(root)
    configure(monkeypatch, value)
    before = {path.relative_to(root) for path in root.rglob("*")}
    result = dataset_validate_blueprint(value, root)
    after = {path.relative_to(root) for path in root.rglob("*")}
    assert result.status == "validated"
    assert after == before


def test_named_tools_categories_signature_and_schema_resource(tmp_path: Path) -> None:
    server = create_mcp_server(tmp_path)
    validate = asyncio.run(server.get_tool("dataset_validate_blueprint")).fn
    materialize = asyncio.run(server.get_tool("dataset_materialize_blueprint")).fn
    assert getattr(validate, "_mcp_category") == "deterministic"
    assert getattr(materialize, "_mcp_category") == "operational"
    parameters = inspect.signature(materialize).parameters
    assert {"approval_id", "approval_revision", "approval_digest"} <= set(parameters)
    assert not {"approved", "accept", "promote"} & set(parameters)

    async def read_schema() -> dict:
        result = await server.read_resource("dataset://schemas/blueprint")
        return json.loads(result.contents[0].content)

    schema = asyncio.run(read_schema())
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) >= {"recipe", "stages", "quality_policy"}


def test_blueprint_modules_cannot_load_executables_or_steal_ownership() -> None:
    root = Path(__file__).resolve().parents[3] / "src" / "factory" / "dataset"
    paths = [*root.glob("runtime/blueprint*.py"), *root.glob("runtime/adapters/blueprint*.py"), root / "mcp/blueprints.py"]
    forbidden_imports = ("factory.agent", "factory.evals", "factory.workflow", "factory.machine_learning")
    forbidden_calls = {"eval", "exec", "compile", "__import__", "import_module"}
    failures: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(forbidden_imports):
                failures.append(f"{path}: import {node.module}")
            if isinstance(node, ast.Import):
                failures.extend(f"{path}: import {alias.name}" for alias in node.names if alias.name.startswith(forbidden_imports))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                failures.append(f"{path}: call {node.func.id}")
    assert not failures

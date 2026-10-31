"""Exact MCP mapping and architecture canaries for the five CAN terminals."""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from factory.machine_learning.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError


class _Operations:
    def __init__(self): self.calls = []
    def _call(self, name, request):
        self.calls.append((name, request))
        return {"status": "failed", "error": f"{name} unavailable"}
    def train(self, request): return self._call("train", request)
    def issue(self, request): return self._call("issue", request)
    def conform(self, request): return self._call("conform", request)
    def promote(self, request): return self._call("promote", request)
    def project(self, request): return self._call("project", request)


def test_registered_tools_invoke_exact_static_operation_mapping():
    operations = _Operations()
    server = create_mcp_server(can_lifecycle_service=operations, passport_service=object())
    terminal_ref = {
        "operation": "ml_train_can_portfolio@v1", "attempt_id": "train",
        "request_sha256": "a" * 64, "terminal_sha256": "b" * 64,
    }
    receipt_ref = {
        "operation": "ml_run_can_cold_conformance@v1", "effect_id": "c" * 64,
        "intent_sha256": "d" * 64, "receipt_sha256": "e" * 64,
    }
    invocations = {
        "ml_train_can_portfolio": ({
            "attempt_id": "train", "dataset_request": {"attempt_id": "dataset"},
        }, "train"),
        "ml_issue_can_passports": ({
            "attempt_id": "issue", "training_terminal_ref": terminal_ref,
            "evaluation_pointers": [],
        }, "issue"),
        "ml_run_can_cold_conformance": ({
            "attempt_id": "conform", "passport_refs": [],
        }, "conform"),
        "ml_promote_can_passports": ({
            "attempt_id": "promote", "conformance_receipt_refs": [receipt_ref],
        }, "promote"),
        "ml_project_can_pipeline_result": ({
            "attempt_id": "project", "training_terminal_ref": terminal_ref,
            "promotion_terminal_ref": terminal_ref,
        }, "project"),
    }
    for tool_name, (arguments, operation) in invocations.items():
        tool = asyncio.run(server.get_tool(tool_name))
        result = tool.fn(**arguments)
        assert isinstance(result, ToolResult)
        assert result.ok is False
        assert result.data is None
        assert result.error == f"{operation} unavailable"
    assert [name for name, _ in operations.calls] == [
        "train", "issue", "conform", "promote", "project",
    ]
    train_request = operations.calls[0][1]
    assert train_request == {
        "attempt_id": "train", "dataset_request": {"attempt_id": "dataset"},
        "model_family": "lightgbm", "top_n_can_ids": 5,
        "training_config": {}, "model_config": None, "experiment_name": "",
    }
    assert "dataset_terminal" not in train_request
    assert "training_terminal" not in operations.calls[1][1]
    assert "evidence_records" not in operations.calls[3][1]
    assert "promotion_terminal" not in operations.calls[4][1]
    assert "training_terminal" not in operations.calls[4][1]
    assert "evaluation_pointers" not in operations.calls[4][1]


def test_lifecycle_modules_have_no_cross_internals_or_legacy_orchestrator():
    brick = Path(__file__).parents[3] / "src/factory/machine_learning"
    paths = [
        brick / "mcp/can_lifecycle_tools.py",
        *list((brick / "runtime").glob("can_*lifecycle*.py")),
        *list((brick / "runtime/adapters").glob("local_can_*.py")),
        *[brick / f"runtime/{name}.py" for name in (
            "can_dataset_binding", "can_evals_binding", "can_lightgbm_operation",
            "can_lightgbm_seal", "can_passport_operations", "can_projection",
        )],
    ]
    forbidden = ("factory.dataset.", "factory.evals.", "factory.storage.")
    for path in paths:
        tree = ast.parse(path.read_text())
        imports = [
            node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        ]
        symbols = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        } | {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        assert not any(name.startswith(forbidden) for name in imports), path
        assert "train_can_contracts" not in symbols, path


def test_lifecycle_boundary_rejects_unknown_fields_and_bad_authority_refs():
    server = create_mcp_server(
        can_lifecycle_service=_Operations(), passport_service=object(),
    )
    tool = asyncio.run(server.get_tool("ml_issue_can_passports"))
    valid_ref = {
        "schema_version": "1.0", "operation": "ml_train_can_portfolio@v1",
        "attempt_id": "train", "request_sha256": "a" * 64,
        "terminal_sha256": "b" * 64,
    }
    pointer = {
        "collection": "eval_results", "doc_id": "eval-train",
        "record_kind": "evaluation_run", "schema_version": 2,
        "revision": "v2", "content_hash": "sha256:" + "c" * 64,
    }
    with pytest.raises(SchemaMigrationError, match="extra_forbidden"):
        tool.fn(
            attempt_id="issue", training_terminal_ref=valid_ref,
            evaluation_pointers=[pointer], unexpected=True,
        )
    with pytest.raises(SchemaMigrationError, match="operation identity"):
        tool.fn(
            attempt_id="issue", training_terminal_ref={**valid_ref, "operation": "bad"},
            evaluation_pointers=[pointer],
        )

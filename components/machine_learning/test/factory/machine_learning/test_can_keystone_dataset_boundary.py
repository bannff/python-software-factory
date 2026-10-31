"""MCP-first Dataset ToolResult boundary contracts for the CAN keystone runner."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from factory.machine_learning.runtime.can_keystone_runner import run_keystone_stage
from factory.mcp_utils.interface import get_service, set_service


def _ok(data: dict[str, Any] | None) -> dict[str, Any]:
    return {"schema_version": "v1", "ok": True, "data": data, "error": None, "idempotency_key": None}


def _failed(error: str = "boom") -> dict[str, Any]:
    return {"schema_version": "v1", "ok": False, "data": None, "error": error, "idempotency_key": None}


@pytest.fixture(autouse=True)
def restore_tool_invoker():
    previous = get_service("tool_invoker")
    set_service("tool_invoker", None)
    yield
    set_service("tool_invoker", previous)


def _invoke(tmp_path: Path, responses: list[Any], **kwargs: Any):
    calls: list[tuple[str, dict[str, Any]]] = []
    def invoker(tool_name: str, **arguments: Any) -> Any:
        calls.append((tool_name, arguments))
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
    source_a, source_b = tmp_path / "decoded.jsonl", tmp_path / "context.jsonl"
    source_a.write_text("{}\n")
    source_b.write_text('{"context": true}\n')
    set_service("tool_invoker", invoker)
    return run_keystone_stage(
        "context_augment", "recipe://local/context-augment@1",
        [source_a.as_uri(), source_b.as_uri()], {"merge_strategy": "nearest"},
        tmp_path / "snapshots", tmp_path / "store", "idem-1",
        input_roles=["decoded_can", "environment_context"], poll_interval_s=0,
        poll_timeout_s=kwargs.get("poll_timeout_s", 1),
    ), calls


def test_flat_dataset_tool_sequence_and_payload_contract(tmp_path: Path):
    result, calls = _invoke(tmp_path, [
        _ok({"job_id": "job-1"}), _ok({"status": "running"}),
        _ok({"status": "completed"}),
        _ok({"dataset_uri": "file:///dataset.jsonl", "manifest_uri": "file:///manifest.json"}),
    ])
    assert result == {"job_id": "job-1", "dataset_uri": "file:///dataset.jsonl", "manifest_uri": "file:///manifest.json"}
    assert [name for name, _ in calls] == ["dataset_submit_generation", "dataset_get_job", "dataset_get_job", "dataset_get_artifact"]
    submit = calls[0][1]
    assert set(submit) == {"recipe_uri", "recipe_digest", "context_snapshot_uri", "context_snapshot_digest", "tool_schema_snapshot_uri", "tool_schema_snapshot_digest", "allowed_tools", "input_artifact_uris", "input_artifact_digests", "input_artifact_roles", "fail_closed", "retry_from_checkpoint_only", "idempotency_key", "schema_version", "storage_root"}
    assert submit["input_artifact_roles"] == ["decoded_can", "environment_context"]
    assert len(submit["input_artifact_uris"]) == len(submit["input_artifact_digests"]) == 2
    assert json.loads(Path(submit["context_snapshot_uri"].removeprefix("file://")).read_text()) == {"stage_overrides": {"context_augment": {"merge_strategy": "nearest"}}}
    assert [item["storage_root"] for _, item in calls] == [str(tmp_path / "store")] * 4


@pytest.mark.parametrize("response", [_failed(), None, {}, {"schema_version": "v1", "ok": True, "data": None}])
def test_submit_rejects_failed_null_and_malformed_envelopes(tmp_path: Path, response: Any):
    result, _ = _invoke(tmp_path, [response])
    assert "submit failed" in result["error"]


@pytest.mark.parametrize("response", [_failed(), None, {}, _ok(None)])
def test_status_rejects_failed_null_and_malformed_envelopes(tmp_path: Path, response: Any):
    result, _ = _invoke(tmp_path, [_ok({"job_id": "j"}), response])
    assert "status failed" in result["error"]


@pytest.mark.parametrize("response", [_failed(), None, {}, _ok(None)])
def test_artifact_rejects_failed_null_and_malformed_envelopes(tmp_path: Path, response: Any):
    result, _ = _invoke(tmp_path, [_ok({"job_id": "j"}), _ok({"status": "completed"}), response])
    assert "artifact failed" in result["error"]


def test_running_job_times_out_without_artifact_lookup(tmp_path: Path):
    result, calls = _invoke(tmp_path, [_ok({"job_id": "j"})], poll_timeout_s=0)
    assert "timed out" in result["error"]
    assert [name for name, _ in calls] == ["dataset_submit_generation"]


def test_input_role_parity_fails_before_remote_submit(tmp_path: Path):
    set_service("tool_invoker", lambda *_args, **_kwargs: pytest.fail("must not invoke"))
    result = run_keystone_stage("augment", "recipe://local/context-augment@1", ["file:///a"], {}, tmp_path / "snaps", tmp_path / "store", "idem", input_roles=[])
    assert "input_uris and input_roles must have equal lengths" in result["error"]


def test_production_machine_learning_has_no_dataset_imports():
    root = Path(__file__).parents[5]
    violations: list[str] = []
    for path in (root / "components" / "machine_learning" / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
            if (module and module.startswith("factory.dataset")) or any(name.startswith("factory.dataset") for name in names):
                violations.append(str(path.relative_to(root)))
    assert violations == []

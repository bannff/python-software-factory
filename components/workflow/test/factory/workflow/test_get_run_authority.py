"""Focused authority tests for ``WorkflowOperations.get_run``.

The read fence must enforce tenant parity AND initiating-principal parity when
both sides are set (same-tenant foreign-owner is opaque ``Run not found``),
while preserving tenant-only and legacy principal-less service callers.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from factory.workflow.runtime.envelope import parse_envelope
from factory.workflow.runtime.operations import WorkflowError
from factory.workflow.runtime.runtime import WorkflowRuntime


def _runtime(tmp_path: Path) -> WorkflowRuntime:
    cfg = tmp_path / "cfg"
    (cfg / "workflows").mkdir(parents=True)
    (cfg / "settings.yaml").write_text(yaml.safe_dump({
        "service": {"name": "workflow-module"},
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.sqlite"}},
        "authoring": {"enabled": False}}))
    (cfg / "workflows" / "ex.yaml").write_text(yaml.safe_dump({
        "schema_version": "v1", "id": "ex", "name": "Ex", "version": 1,
        "steps": [{"id": "start", "kind": "noop"}]}))
    return WorkflowRuntime.from_config_dir(cfg)


def _start(runtime, run_id, *, tenant="t", principal=None):
    env = {"run_id": run_id, "tenant_id": tenant}
    if principal is not None:
        env["principal_id"] = principal
    runtime.start_run(workflow_name_or_id="ex", input={}, envelope=parse_envelope(env))


def test_owner_can_read_own_run(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _start(runtime, "r1", principal="alice")
    got = runtime.get_run(run_id="r1",
                          envelope=parse_envelope({"tenant_id": "t", "principal_id": "alice"}))
    assert got["run_id"] == "r1"


def test_same_tenant_foreign_owner_is_opaque(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _start(runtime, "r1", principal="alice")
    with pytest.raises(WorkflowError, match="Run not found"):
        runtime.get_run(run_id="r1",
                        envelope=parse_envelope({"tenant_id": "t", "principal_id": "mallory"}))


def test_cross_tenant_is_opaque(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _start(runtime, "r1", tenant="t", principal="alice")
    with pytest.raises(WorkflowError, match="Run not found"):
        runtime.get_run(run_id="r1",
                        envelope=parse_envelope({"tenant_id": "other", "principal_id": "alice"}))


def test_tenant_only_caller_preserved(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _start(runtime, "r1", principal="alice")
    # No principal in the reading envelope -> principal parity is not enforced.
    got = runtime.get_run(run_id="r1", envelope=parse_envelope({"tenant_id": "t"}))
    assert got["run_id"] == "r1"


def test_legacy_principal_less_run_preserved(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _start(runtime, "r1")  # no initiating principal recorded
    got = runtime.get_run(run_id="r1",
                          envelope=parse_envelope({"tenant_id": "t", "principal_id": "anyone"}))
    assert got["run_id"] == "r1"

"""Authoring upsert/delete must refresh the live registry (#340)."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

from factory.workflow.runtime.envelope import parse_envelope
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.server import create_mcp_server

_DEF = {
    "schema_version": "v1", "name": "Live Test", "version": 1,
    "steps": [{"id": "start", "kind": "noop"}],
}


@pytest.fixture
def runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WorkflowRuntime:
    monkeypatch.setenv("WORKFLOW_ENABLE_AUTHORING_TOOLS", "1")
    cfg = tmp_path / "config"
    (cfg / "workflows").mkdir(parents=True)
    (cfg / "settings.yaml").write_text(yaml.safe_dump({
        "service": {"name": "workflow-module"},
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.sqlite"}},
        "executor": {"backend": "local"},
        "authoring": {"enabled": True},
    }))
    return WorkflowRuntime.from_config_dir(cfg)


def _tool(mcp, name: str):
    return asyncio.run(mcp.get_tool(name)).fn


def _ids(runtime: WorkflowRuntime) -> set[str]:
    return {w["id"] for w in runtime.get_workflow_registry()}


def _start(runtime: WorkflowRuntime, ref: str) -> dict:
    return runtime.start_run(
        workflow_name_or_id=ref, input={},
        envelope=parse_envelope({"tenant_id": "t"}),
    )


def test_upsert_makes_workflow_runnable_and_delete_removes_it(runtime) -> None:
    mcp = create_mcp_server(runtime)
    upsert = _tool(mcp, "workflow.authoring.upsert_workflow_definition")
    delete = _tool(mcp, "workflow.authoring.delete_workflow_definition")

    assert upsert(id="lc-test", yaml_or_object=_DEF).ok
    assert "lc-test" in _ids(runtime)
    assert _start(runtime, "lc-test")["run_id"]
    assert _start(runtime, "Live Test")["run_id"]

    assert delete(id="lc-test").data.deleted
    assert "lc-test" not in _ids(runtime)
    with pytest.raises(Exception):
        _start(runtime, "lc-test")
    with pytest.raises(Exception):
        _start(runtime, "Live Test")


def test_dry_run_upsert_leaves_registry_unchanged(runtime) -> None:
    upsert = _tool(create_mcp_server(runtime), "workflow.authoring.upsert_workflow_definition")
    assert upsert(id="dry", yaml_or_object=_DEF, dry_run=True).ok
    assert "dry" not in _ids(runtime)

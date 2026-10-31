from __future__ import annotations

import pytest
import yaml

from factory.auth.interface import Runtime, WorkloadGrant


def _grant() -> WorkloadGrant:
    return WorkloadGrant.create(
        launch_id="launch", generation=1, tenant_id="tenant",
        audience="companion-x", allowed_tools=["graph_get_entity"],
    )


def test_direct_runtime_is_fail_closed_without_injected_provider(tmp_path) -> None:
    (tmp_path / "backends").mkdir()
    (tmp_path / "settings.yaml").write_text(yaml.safe_dump({
        "service_name": "test", "backend": "memory"}))
    (tmp_path / "backends" / "memory.yaml").write_text("kind: memory\n")
    runtime = Runtime(tmp_path)
    with pytest.raises(RuntimeError, match="not configured"):
        runtime.issue_workload_credential(
            _grant(), workflow_run_id="run", attempt_id="a", revision=0)


def test_conflicting_worker_declarations_fail_closed(monkeypatch) -> None:
    from factory.auth.server import get_workload_credential_provider

    monkeypatch.setenv("MCP_WORKLOAD_LOCAL_SINGLE_PROCESS", "true")
    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    monkeypatch.setenv("UVICORN_WORKERS", "4")
    with pytest.raises(ValueError, match="exactly one worker"):
        get_workload_credential_provider()

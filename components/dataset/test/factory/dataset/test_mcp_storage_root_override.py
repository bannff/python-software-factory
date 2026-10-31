"""Per-call Dataset MCP storage-root override contracts."""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.dataset.mcp import deterministic, operational


class _Result:
    def __init__(self, payload: dict):
        self.payload = payload

    def model_dump(self, mode: str) -> dict:
        assert mode == "json"
        return self.payload


def _tool(mcp: ToolCatalog, name: str):
    tool = asyncio.run(mcp.get_tool(name)).fn

    def invoke(*args, **kwargs):
        bound = inspect.signature(tool.__wrapped__).bind(*args, **kwargs)
        result = tool(dict(bound.arguments)).data
        return result.root

    return invoke


def test_full_lifecycle_uses_per_call_storage_root(tmp_path, monkeypatch):
    registered = tmp_path / "registered"
    override = tmp_path / "override"
    roots: list[tuple[str, Path | None]] = []

    def submit(_request, root):
        roots.append(("submit", root))
        return _Result({"job_id": "job-1"})

    def status(_job_id, root):
        roots.append(("status", root))
        return _Result({"job_id": "job-1", "status": "completed"})

    def cancel(_job_id, _reason, root):
        roots.append(("cancel", root))
        return _Result({"job_id": "job-1", "status": "failed"})

    def artifact(_job_id, root):
        roots.append(("artifact", root))
        return _Result({"dataset_uri": "file:///dataset", "manifest_uri": "file:///manifest"})

    def manifest(_dataset_uri, root):
        roots.append(("resolve", root))
        return _Result({"dataset_uri": "file:///dataset"})

    monkeypatch.setattr(operational, "dataset_submit_generation", submit)
    monkeypatch.setattr(operational, "dataset_get_job", status)
    monkeypatch.setattr(operational, "dataset_cancel_job", cancel)
    monkeypatch.setattr(deterministic, "dataset_get_artifact", artifact)
    monkeypatch.setattr(deterministic, "dataset_resolve_artifact", manifest)
    mcp = ToolCatalog("dataset-storage-root")
    operational.register(mcp, registered)
    deterministic.register(mcp, registered)

    receipt = _tool(mcp, "dataset_submit_generation")(
        "recipe://local/pass-through@1", "a" * 64,
        "file:///context", "b" * 64, "file:///tools", "c" * 64,
        storage_root=str(override),
    )
    observed = _tool(mcp, "dataset_get_job")(
        "job-1", storage_root=str(override),
    )
    resolved = _tool(mcp, "dataset_get_artifact")(
        "job-1", storage_root=str(override),
    )
    manifest_result = _tool(mcp, "dataset_resolve_artifact")(
        "file:///dataset", storage_root=str(override),
    )
    cancelled = _tool(mcp, "dataset_cancel_job")(
        "job-1", storage_root=str(override),
    )

    assert receipt == {"job_id": "job-1"}
    assert observed["status"] == "completed"
    assert resolved["dataset_uri"] == "file:///dataset"
    assert manifest_result["dataset_uri"] == "file:///dataset"
    assert cancelled["status"] == "failed"
    assert roots == [
        ("submit", override), ("status", override), ("artifact", override),
        ("resolve", override), ("cancel", override),
    ]

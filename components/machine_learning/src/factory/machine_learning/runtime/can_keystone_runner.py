"""Keystone CAN pipeline — per-stage submit + poll runner.

Dataset work crosses the canonical project-level ``tool_invoker`` service;
Machine Learning never imports the Dataset runtime.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .can_keystone_dataset_payload import build_dataset_request
from .can_keystone_helpers import _get_invoker

_POLL_INTERVAL_S = 1.0
_POLL_TIMEOUT_S = 600.0
_VALID_JOB_STATES = frozenset({"queued", "running", "completed", "failed"})


def _unwrap(result: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Accept only a serialized v1 ToolResult with object success data."""
    if not isinstance(result, dict) or result.get("schema_version") != "v1":
        return None, "invalid MCP envelope"
    if result.get("ok") is not True:
        return None, str(result.get("error") or "remote failure")
    data = result.get("data")
    if not isinstance(data, dict):
        return None, "invalid MCP success data"
    return data, None


def run_keystone_stage(
    stage: str, recipe_uri: str, input_uris: list[str],
    context_config: dict[str, Any], snaps: Path, root: Path,
    idempotency_key: str,
    *,
    input_roles: list[str] | None = None,
    poll_interval_s: float = _POLL_INTERVAL_S,
    poll_timeout_s: float = _POLL_TIMEOUT_S,
) -> dict[str, Any]:
    """Submit and observe one Dataset stage through the MCP tool invoker."""
    invoker = _get_invoker()
    if invoker is None:
        return {"error": f"{stage} submit failed: tool_invoker unavailable"}
    try:
        request = build_dataset_request(
            recipe_uri, input_uris, context_config, snaps, idempotency_key,
            input_roles=input_roles,
        )
        receipt = invoker(
            "dataset_submit_generation", **request, storage_root=str(root),
        )
    except Exception as exc:
        return {"error": f"{stage} submit failed: {exc}"}
    receipt, error = _unwrap(receipt)
    if error:
        return {"error": f"{stage} submit failed: {error}"}
    assert receipt is not None
    job_id = receipt.get("job_id")
    if not job_id:
        return {"error": f"{stage} submit failed: invalid receipt"}

    deadline = time.monotonic() + poll_timeout_s
    status: dict[str, Any] | None = None
    state = None
    while time.monotonic() < deadline:
        try:
            observed = invoker(
                "dataset_get_job", job_id=job_id, storage_root=str(root),
            )
        except Exception as exc:
            return {"error": f"{stage} status failed: {exc}", "job_id": job_id}
        observed, error = _unwrap(observed)
        if error:
            return {"error": f"{stage} status failed: {error}", "job_id": job_id}
        assert observed is not None
        status = observed
        state = status.get("status")
        if state not in _VALID_JOB_STATES:
            return {
                "error": f"{stage} status failed: invalid status {state!r}",
                "job_id": job_id,
            }
        if state in {"completed", "failed"}:
            break
        time.sleep(poll_interval_s)
    else:
        return {"error": f"{stage} timed out after {poll_timeout_s}s", "job_id": job_id}
    if state == "failed":
        return {"error": status.get("error") or f"{stage} failed", "job_id": job_id}

    try:
        artifact = invoker(
            "dataset_get_artifact", job_id=job_id, storage_root=str(root),
        )
    except Exception as exc:
        return {"error": f"{stage} artifact failed: {exc}", "job_id": job_id}
    artifact, error = _unwrap(artifact)
    if error:
        return {"error": f"{stage} artifact failed: {error}", "job_id": job_id}
    assert artifact is not None
    dataset_uri = artifact.get("dataset_uri")
    manifest_uri = artifact.get("manifest_uri")
    artifact_digest = artifact.get("digest")
    if not dataset_uri or not manifest_uri:
        return {"error": f"{stage} artifact failed: invalid response", "job_id": job_id}
    result = {
        "job_id": job_id,
        "dataset_uri": dataset_uri,
        "manifest_uri": manifest_uri,
    }
    if artifact_digest:
        result["digest"] = artifact_digest
    return result


__all__ = ["run_keystone_stage"]

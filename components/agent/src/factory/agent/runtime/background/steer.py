"""Live steering for a Workflow-owned background Agent attempt."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import get_envelope, normalize_envelope

from ..managed_steering import managed_steering
from .launch import BackgroundLaunchError, _call


async def steer_background(run_id: str, send_id: str, content: str) -> dict[str, Any]:
    envelope = normalize_envelope(get_envelope())
    if not envelope.get("tenant_id") or not envelope.get("principal_id"):
        raise BackgroundLaunchError("background_identity_required")
    run = await _call(
        "workflow", "get_run", {"run_id": run_id, "envelope": envelope},
        envelope, f"background-steer-read:{run_id}:{send_id}",
    )
    initiation = run.get("initiation_envelope", {})
    if initiation.get("principal_id") != envelope.get("principal_id"):
        raise BackgroundLaunchError("background_run_not_found")
    metadata = run.get("input", {}).get("launch_metadata", {})
    if metadata.get("kind") != "background_subagent":
        raise BackgroundLaunchError("background_run_not_found")
    delivery = await managed_steering.offer(run_id, send_id, content)
    if delivery is None:
        raise BackgroundLaunchError("background_not_running")
    return {
        "run_id": run_id, "send_id": delivery.send_id,
        "state": "written", "revision": delivery.revision,
    }


__all__ = ["steer_background"]

"""Query Workflow runs for background subagent/loop-cycle launches only.

Reuses the same in-process tool-invoker seam ``launch.py`` uses to call other
bricks — no direct import of Workflow internals, and no new Workflow filter:
``launch_metadata`` already lands on every background-launched run's
``input`` (``launch.py`` writes it), so this is a read + client-side filter,
not new substrate.
"""
from __future__ import annotations

import asyncio
from typing import Any

from factory.mcp_utils.interface import get_service

_BACKGROUND_KINDS = frozenset({"background_subagent", "workflow_loop_cycle"})
_ACTIVE_STATUSES = frozenset({"pending", "running", "waiting"})


class BackgroundListError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def list_background_runs(
    envelope: dict[str, Any], origin_thread_id: str | None,
    active_only: bool, limit: int,
) -> list[dict[str, str]]:
    factory = get_service("tool_invoker_for_caller")
    invoker = factory("agent") if callable(factory) else None
    if not callable(invoker):
        raise BackgroundListError("background_runtime_unavailable")
    raw = await asyncio.to_thread(
        invoker, {"brick_name": "workflow", "tool_name": "workflow.list_runs"},
        arguments={"filter": {}, "pagination": {"limit": max(limit, 200)}},
        idempotency_key=None, envelope=envelope,
    )
    if not isinstance(raw, dict) or raw.get("ok") is not True:
        raise BackgroundListError("workflow_transport_failed")
    structured = raw.get("result", {}).get("structured_content")
    if not isinstance(structured, dict) or structured.get("ok") is not True:
        raise BackgroundListError("workflow_list_runs_failed")
    runs = structured.get("data", {}).get("runs", []) if isinstance(structured.get("data"), dict) else []
    return _filtered(runs, origin_thread_id, active_only, limit)


def _filtered(
    runs: list[Any], origin_thread_id: str | None, active_only: bool, limit: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        metadata = run.get("input", {}).get("launch_metadata")
        if not isinstance(metadata, dict) or metadata.get("kind") not in _BACKGROUND_KINDS:
            continue
        if origin_thread_id and metadata.get("origin_thread_id") != origin_thread_id:
            continue
        if active_only and run.get("status") not in _ACTIVE_STATUSES:
            continue
        rows.append({
            "run_id": str(run.get("run_id", "")), "persona_id": str(metadata.get("persona_id", "")),
            "status": str(run.get("status", "")), "kind": str(metadata.get("kind", "")),
            "origin_thread_id": str(metadata.get("origin_thread_id", "")),
            "started_at": str(run.get("started_at", "")),
        })
        if len(rows) >= limit:
            break
    return rows


__all__ = ["BackgroundListError", "list_background_runs"]

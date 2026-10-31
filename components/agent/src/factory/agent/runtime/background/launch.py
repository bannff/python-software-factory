"""Launch one registered persona as a Workflow-owned background attempt."""
from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from factory.mcp_utils.interface import get_envelope, get_service, normalize_envelope

from ..managed_launch import launch_managed_graph, new_run_key
from .persona_graph import persona_graph


class BackgroundLaunchError(RuntimeError):
    """Stable background launch failure classification."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def launch_background(
    registry: Any, agent_id: str, task: str, launch_id: str | None,
    supplied_context: dict[str, str] | None = None,
    output_schema: str | None = None, delivery_mode: str = "origin",
    loop_id: str | None = None, loop_cycle: int | None = None,
) -> dict[str, str]:
    """Admit durably, schedule drive, and return before provider execution."""
    try:
        config = persona_graph(registry, agent_id, output_schema)
    except ValueError as exc:
        raise BackgroundLaunchError("unknown_agent_id") from exc
    envelope = normalize_envelope(get_envelope())
    origin = await _origin_session(envelope)
    submit = get_service("background_task_launcher")
    if not callable(submit):
        raise BackgroundLaunchError("background_runtime_unavailable")
    run_key = new_run_key(config.id, requested=launch_id)
    background_thread = f"bg_{hashlib.sha256(run_key.encode()).hexdigest()[:32]}"
    persona = registry.get(agent_id)
    child = await _call("session", "ensure_thread", {
        "thread_id": background_thread,
        "title": f"Background: {task.strip().splitlines()[0][:188]}",
        "agent_id": agent_id, "model": str(getattr(persona, "model", "unknown")),
        "envelope": envelope,
    }, envelope, f"background-session:{run_key}")
    loop_context = ({"loop_id": loop_id or "", "loop_cycle": str(loop_cycle)}
                    if delivery_mode == "workflow_loop" else {})
    context = {
        **(supplied_context or {}), **loop_context,
        "origin_session_id": origin["session_id"],
        "origin_thread_id": origin["thread_id"],
        "background_session_id": child["session"]["session_id"],
        "background_thread_id": background_thread,
        "persona_id": agent_id,
    }
    launch_kind = ("workflow_loop_cycle" if delivery_mode == "workflow_loop"
                   else "background_subagent")
    result = await launch_managed_graph(
        config, task, context, run_key=run_key, origin_kind="dynamic",
        invocation_state={"kind": launch_kind, **context},
        envelope=envelope, execute=False,
        launch_metadata={
            "kind": launch_kind,
            "origin_session_id": origin["session_id"],
            "origin_thread_id": origin["thread_id"],
            "background_session_id": child["session"]["session_id"],
            "background_thread_id": background_thread,
            "persona_id": agent_id, **loop_context,
        },
    )
    submit(_drive(result.run_id, envelope))
    return {
        "run_id": result.run_id, "run_key": result.run_key,
        "status": result.status, "agent_id": agent_id,
        "origin_session_id": origin["session_id"],
    }


async def _origin_session(envelope: dict[str, Any]) -> dict[str, Any]:
    thread_id = str(envelope.get("thread_id") or envelope.get("session_id") or "")
    if not thread_id or not envelope.get("tenant_id") or not envelope.get("principal_id"):
        raise BackgroundLaunchError("origin_session_required")
    payload = await _call("session", "resolve_thread", {
        "thread_id": thread_id, "envelope": envelope,
    }, envelope, f"background-origin:{thread_id}")
    session = payload.get("session") if isinstance(payload, dict) else None
    if not isinstance(session, dict):
        raise BackgroundLaunchError("origin_session_not_found")
    return session


async def _drive(run_id: str, envelope: dict[str, Any]) -> None:
    await _call(
        "workflow", "resume_run", {"run_id": run_id, "envelope": envelope},
        envelope, f"background-drive:{run_id}",
    )


async def _call(
    brick: str, tool: str, arguments: dict[str, Any],
    envelope: dict[str, Any], idempotency_key: str,
) -> dict[str, Any]:
    factory = get_service("tool_invoker_for_caller")
    invoker = factory("agent") if callable(factory) else None
    if not callable(invoker):
        raise BackgroundLaunchError("background_runtime_unavailable")
    raw = await asyncio.to_thread(
        invoker, {"brick_name": brick, "tool_name": tool},
        arguments=arguments, idempotency_key=idempotency_key, envelope=envelope,
    )
    if not isinstance(raw, dict) or raw.get("ok") is not True:
        raise BackgroundLaunchError(f"{brick}_transport_failed")
    structured = raw.get("result", {}).get("structured_content")
    if not isinstance(structured, dict) or structured.get("ok") is not True:
        raise BackgroundLaunchError(f"{brick}_{tool}_failed")
    data = structured.get("data")
    return data if isinstance(data, dict) else {}


__all__ = ["BackgroundLaunchError", "launch_background"]

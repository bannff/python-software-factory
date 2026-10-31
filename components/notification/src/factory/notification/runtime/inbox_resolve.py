"""Owner-scoped deep-link source reauthorization for the durable inbox.

The resolver never imports a source brick's runtime. Given a validated
:class:`NotificationTarget`, it re-checks ambient authority against the owning
source brick strictly through the caller-bound MCP invoker
(``tool_invoker_for_caller("notification")``) under the owner's ambient
envelope with NO service binding kwargs. Only a transport-successful, typed,
successful source ``ToolResult`` carrying data authorizes; every other
outcome — absent / foreign / deleted / malformed source, transport failure,
unexpected payload, unsupported target, or invoker absence — raises the single
opaque :class:`TargetNotResolved`. The resolver never returns source payload,
a URL, or a route: the frontend maps the closed ``(kind, id)`` to navigation.
"""
from __future__ import annotations

from typing import Any, Callable

from .inbox_targets import target_id, target_kind

# kind -> (brick, tool, id-argument-name, pass-owner-envelope-as-argument).
# Every kind reads ambient authority from the invoker-set envelope EXCEPT
# ``workflow.get_run`` which owner-scopes off its ``envelope`` argument, so the
# owner envelope is forwarded there explicitly (it is not a service binding).
_SOURCE_READS: dict[str, tuple[str, str, str, bool]] = {
    "session": ("session", "session_get", "session_id", False),
    "workflow_run": ("workflow", "workflow.get_run", "run_id", True),
    "schedule": ("scheduler", "scheduler_get", "schedule_id", False),
    "artifact": ("artifacts", "artifacts_get", "slug", False),
    "crew": ("agent", "agent_get_crew", "crew_id", False),
    "lesson": ("lessons", "lessons_get", "lesson_id", False),
    "canvas": ("ui", "ui_resolve_canvas", "view_id", False),
}

_CALLER = "notification"


class TargetNotResolved(Exception):
    """One opaque outcome for every resolution deviation. Carries no detail."""


def _source_authorized(transport: Any) -> bool:
    """True only for a transport-ok, typed, successful source ``ToolResult``."""
    if not isinstance(transport, dict) or transport.get("ok") is not True:
        return False
    result = transport.get("result")
    if not isinstance(result, dict) or result.get("kind") != "tool":
        return False
    structured = result.get("structured_content")
    if not isinstance(structured, dict):
        return False
    return structured.get("ok") is True and structured.get("data") is not None


def authorize_target(
    target: Any, *, invoker_factory: Callable[[str], Any] | None,
    envelope: dict[str, Any], idempotency_key: str,
) -> None:
    """Re-check ambient authority against the owning source brick or raise."""
    route = _SOURCE_READS.get(target_kind(target))
    if route is None:
        raise TargetNotResolved()
    brick, tool, id_arg, pass_envelope = route
    invoker = invoker_factory(_CALLER) if callable(invoker_factory) else None
    if not callable(invoker):
        raise TargetNotResolved()
    arguments: dict[str, Any] = {id_arg: target_id(target)}
    if pass_envelope:
        arguments["envelope"] = dict(envelope)
    try:
        transport = invoker(
            {"brick_name": brick, "tool_name": tool},
            arguments=arguments, idempotency_key=idempotency_key,
            envelope=dict(envelope),
        )
    except Exception as exc:  # noqa: BLE001 — one opaque outcome, no detail
        raise TargetNotResolved() from exc
    if not _source_authorized(transport):
        raise TargetNotResolved()


__all__ = ["TargetNotResolved", "authorize_target"]

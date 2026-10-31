"""Envelope context — async-safe per-request principal propagation.

Uses ``contextvars.ContextVar`` so each asyncio Task inherits the
envelope set by its parent coroutine.  Mutations inside a child task
do NOT propagate back to the parent — this is standard contextvars
behaviour and exactly what we want for request-scoped state.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_envelope_var: ContextVar[dict[str, Any] | None] = ContextVar(
    "mcp_envelope", default=None,
)

_ENVELOPE_CONTEXT_KEYS = frozenset({
    "tenant_id", "producer_id", "principal_id", "visibility", "source_namespace",
    "session_id", "request_id", "correlation_id", "workflow_id", "run_id",
    "workflow_run_id", "trace_id", "span_id", "tracestate", "parent_span_id",
    "agent_id", "tool_name", "attributes",
})


def set_envelope(envelope: dict[str, Any]) -> Token:
    """Set the per-request envelope (returns a reset token)."""
    return _envelope_var.set(envelope)


def normalize_envelope(envelope: dict[str, Any] | None) -> dict[str, Any]:
    """Canonicalize ingress run aliases without emitting workflow_run_id."""
    normalized = dict(envelope or {})
    run_id = normalized.get("run_id")
    workflow_run_id = normalized.get("workflow_run_id")
    if run_id and workflow_run_id and str(run_id).strip() != str(workflow_run_id).strip():
        raise ValueError("conflicting run_id/workflow_run_id")
    canonical = run_id or workflow_run_id
    normalized.pop("workflow_run_id", None)
    if canonical:
        normalized["run_id"] = canonical
    else:
        normalized.pop("run_id", None)
    return normalized


def envelope_updates_from_mapping(values: dict[str, Any] | None) -> dict[str, Any]:
    """Extract only envelope-contract fields from a broader context mapping."""
    if not isinstance(values, dict):
        return {}
    return normalize_envelope({
        key: value
        for key, value in values.items()
        if key in _ENVELOPE_CONTEXT_KEYS and value is not None
    })


def push_envelope_updates(**updates: Any) -> Token:
    """Merge updates into the current envelope and normalize correlation IDs."""
    envelope = dict(get_envelope() or {})
    for key, value in updates.items():
        if value is not None:
            envelope[key] = value
    return set_envelope(normalize_envelope(envelope))


def reset_envelope(token: Token | None) -> None:
    """Restore the previous envelope after a scoped update."""
    if token is not None:
        token.var.reset(token)


def get_envelope() -> dict[str, Any] | None:
    """Return the current envelope, or *None* outside a request."""
    return _envelope_var.get()


def get_principal_id() -> str | None:
    """Convenience: extract ``principal_id`` from the current envelope."""
    env = _envelope_var.get()
    return env.get("principal_id") if env else None


def get_session_id() -> str | None:
    """Convenience: extract ``session_id`` from the current envelope."""
    env = _envelope_var.get()
    return env.get("session_id") if env else None


def get_workflow_run_id() -> str | None:
    """Convenience: extract ``workflow_run_id`` from the current envelope."""
    env = _envelope_var.get()
    if not env:
        return None
    return env.get("workflow_run_id") or env.get("run_id")


def get_run_id() -> str | None:
    """Convenience: extract ``run_id`` from the current envelope."""
    env = _envelope_var.get()
    if not env:
        return None
    return env.get("run_id") or env.get("workflow_run_id")


# ── Caller hint ──────────────────────────────────────────────────────────

_caller_hint_var: ContextVar[str | None] = ContextVar("mcp_caller_hint", default=None)


def set_caller_hint(hint: str | None) -> Token:
    """Set a caller hint for the current context (e.g. 'system:warmup').

    Returns a reset token (standard contextvars pattern).
    """
    return _caller_hint_var.set(hint)


def get_caller_hint() -> str | None:
    """Get the current caller hint, or None."""
    return _caller_hint_var.get()

"""Canonical input and caller identity for MCP idempotency replay."""
from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass
from typing import Any, Callable

from factory.mcp_utils.context import get_caller_hint, get_envelope
from factory.mcp_utils.runtime.bounded_json import is_bounded_json, to_plain_json

_MAX_INPUT_BYTES = 1 * 1024 * 1024
_STABLE_CONTEXT = (
    "tenant_id", "principal_id", "session_id", "workflow_id", "run_id",
    "workflow_run_id", "agent_id",
)


@dataclass(frozen=True)
class ReplayIdentity:
    scope: str
    key: str
    context_digest: str
    input_digest: str


def build_identity(
    scope: str, key: str, func: Callable[..., Any], args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> ReplayIdentity | None:
    """Build a canonical replay identity; disable replay without stable context."""
    input_digest = _digest(_bound_arguments(func, args, kwargs))
    context = _context_projection(kwargs)
    if not context:
        return None
    return ReplayIdentity(scope, key, _digest(context), input_digest)


def _bound_arguments(
    func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any],
) -> dict[str, Any]:
    try:
        bound = inspect.signature(func).bind(*args, **kwargs)
        bound.apply_defaults()
        values = dict(bound.arguments)
    except (TypeError, ValueError) as exc:
        raise ValueError("idempotent input cannot be canonically bound") from exc
    values.pop("idempotency_key", None)
    for name, value in tuple(values.items()):
        if name == "kwargs" and isinstance(value, dict):
            values[name] = {k: v for k, v in value.items() if k != "idempotency_key"}
    return values


def _context_projection(kwargs: dict[str, Any]) -> dict[str, Any]:
    envelope = get_envelope() or {}
    values = {key: envelope.get(key, kwargs.get(key)) for key in _STABLE_CONTEXT}
    hint = get_caller_hint()
    if hint:
        values["caller_hint"] = hint
    return {key: value for key, value in values.items() if value not in (None, "")}


def _digest(value: Any) -> str:
    plain = to_plain_json(value)
    if not is_bounded_json(plain):
        raise ValueError("idempotent input is not bounded JSON")
    try:
        encoded = json.dumps(
            plain, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("idempotent input is not canonical JSON") from exc
    if len(encoded) > _MAX_INPUT_BYTES:
        raise ValueError("idempotent input exceeds the canonical size limit")
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["ReplayIdentity", "build_identity"]

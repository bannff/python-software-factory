"""Orthogonal service-only policy and one-shot protected invocation state."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, TypeVar

from .service_bindings import (
    BindingKind, binding_kind, binding_matches,
)
from .service_claims import (
    InternalInvocationClaims, mint_internal_invocation_claims,
)

F = TypeVar("F", bound=Callable[..., Any])


class ServiceOnlyAccessError(PermissionError):
    """Raised before a service-only handler can execute."""


@dataclass(slots=True)
class _InvocationState:
    claims: InternalInvocationClaims
    consumed: bool = False
    entry_issued: bool = False
    closed: bool = False
    owner: asyncio.Task[Any] | None = None
    lock: Lock = field(default_factory=Lock)


_claims_var: ContextVar[_InvocationState | None] = ContextVar(
    "mcp_internal_invocation_claims", default=None,
)


def _function(value: Any) -> Any:
    return getattr(value, "fn", value)


def service_only(
    *, callers: set[str] | frozenset[str], binding: BindingKind,
) -> Callable[[F], F]:
    """Mark a typed tool as callable only by named in-process services."""
    normalized = frozenset(c.strip() for c in callers if isinstance(c, str) and c.strip())
    if not normalized or len(normalized) != len(callers):
        raise ValueError("service_only callers must be non-empty unique strings")
    if binding not in (
        "enrollment", "attempt", "execution", "protected_artifact",
        "credential_slot", "credential_egress", "steer", "completion",
        "lesson_proposal", "projection", "migration_import",
    ):
        raise ValueError(
            "service_only binding must be enrollment, attempt, execution, "
            "protected_artifact, credential_slot, credential_egress, steer, "
            "completion, lesson_proposal, projection, or migration_import"
        )

    def decorate(func: F) -> F:
        setattr(func, "_mcp_service_callers", normalized)
        setattr(func, "_mcp_service_binding", binding)
        return func

    return decorate


def service_callers(value: Any) -> frozenset[str]:
    callers = getattr(_function(value), "_mcp_service_callers", None)
    return callers if isinstance(callers, frozenset) else frozenset()


def service_binding(value: Any) -> BindingKind | None:
    kind = getattr(_function(value), "_mcp_service_binding", None)
    return kind if kind in (
        "enrollment", "attempt", "execution", "protected_artifact",
        "credential_slot", "credential_egress", "steer", "completion",
        "lesson_proposal", "projection", "migration_import",
    ) else None


def is_service_only(value: Any) -> bool:
    return bool(service_callers(value))


def set_internal_invocation_claims(claims: InternalInvocationClaims) -> Token:
    if not isinstance(claims, InternalInvocationClaims):
        raise TypeError("claims must be minted InternalInvocationClaims")
    return _claims_var.set(_InvocationState(claims))


def reset_internal_invocation_claims(token: Token | None) -> None:
    if token is not None:
        token.var.reset(token)


def get_internal_invocation_claims() -> InternalInvocationClaims | None:
    state = _claims_var.get()
    return state.claims if state is not None else None


def _validate(
    state: _InvocationState, value: Any, audience: str,
    target_tool: str, arguments: dict[str, Any],
) -> None:
    claims = state.claims
    expected_kind = service_binding(value)
    if claims.caller not in service_callers(value):
        raise ServiceOnlyAccessError("internal caller is not authorized")
    if claims.audience != audience or claims.target_tool != target_tool:
        raise ServiceOnlyAccessError("internal resolved target claim mismatch")
    if claims._target is not _function(value):
        raise ServiceOnlyAccessError("internal wrapper permit mismatch")
    if expected_kind is None or binding_kind(claims.binding) != expected_kind:
        raise ServiceOnlyAccessError("internal operation binding mismatch")
    if not binding_matches(claims.binding, arguments):
        raise ServiceOnlyAccessError("internal operation fields mismatch")


def begin_service_invocation(
    value: Any, *, audience: str, target_tool: str, arguments: dict[str, Any],
) -> _InvocationState | None:
    """Consume one raw-argument authorization before FastMCP validation."""
    if not is_service_only(value):
        return None
    if getattr(_function(value), "_mcp_input_model", None) is None:
        raise ServiceOnlyAccessError("service-only tools require a typed input boundary")
    state = _claims_var.get()
    if state is None:
        raise ServiceOnlyAccessError("internal invocation claims are required")
    with state.lock:
        if state.consumed or state.closed:
            raise ServiceOnlyAccessError("internal invocation claims are already consumed")
        _validate(state, value, audience, target_tool, arguments)
        state.owner = asyncio.current_task()
        state.consumed = True
    return state


def acquire_service_entry(value: Any) -> object | None:
    """Issue the opaque permit only to the dispatch task and exact wrapper."""
    if not is_service_only(value):
        return None
    state = _claims_var.get()
    if state is None:
        raise ServiceOnlyAccessError("service-only boundary requires native dispatch")
    with state.lock:
        if state.closed or not state.consumed or state.entry_issued:
            raise ServiceOnlyAccessError("service-only entry permit is unavailable")
        if state.owner is not asyncio.current_task() or state.claims._target is not value:
            raise ServiceOnlyAccessError("service-only entry permit owner mismatch")
        state.entry_issued = True
        return state.claims._permit


def authorize_service_boundary(
    value: Any, args: tuple[Any, ...], arguments: dict[str, Any], entry: object,
) -> None:
    """Verify exact typed-wrapper entry before DTO validation or idempotency."""
    if not is_service_only(value):
        return
    state = _claims_var.get()
    raw = dict(args[0]) if len(args) == 1 and isinstance(args[0], dict) \
        and not arguments else dict(arguments)
    if state is None:
        raise ServiceOnlyAccessError("service-only boundary requires native dispatch")
    with state.lock:
        if state.closed or not state.consumed or not state.entry_issued:
            raise ServiceOnlyAccessError("service-only entry permit is unavailable")
        if state.claims._target is not value or entry is not state.claims._permit:
            raise ServiceOnlyAccessError("service-only wrapper permit mismatch")
        if not binding_matches(state.claims.binding, raw):
            raise ServiceOnlyAccessError("internal operation fields mismatch")


def end_service_invocation(state: _InvocationState | None) -> None:
    if state is not None:
        with state.lock:
            state.closed = True


__all__ = [
    "InternalInvocationClaims", "ServiceOnlyAccessError", "service_only",
    "service_callers", "service_binding", "is_service_only",
    "mint_internal_invocation_claims", "set_internal_invocation_claims",
    "reset_internal_invocation_claims", "get_internal_invocation_claims",
    "begin_service_invocation", "acquire_service_entry",
    "authorize_service_boundary", "end_service_invocation",
]

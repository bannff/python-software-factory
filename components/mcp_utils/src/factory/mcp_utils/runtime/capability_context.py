"""Async-safe ambient authority for effective MCP capability scopes."""
from __future__ import annotations

from contextvars import ContextVar, Token

from .scoped_capabilities import CapabilityScope

_CURRENT_SCOPE: ContextVar[CapabilityScope | None] = ContextVar(
    "effective_capability_scope", default=None,
)


def bind_capability_scope(scope: CapabilityScope) -> Token[CapabilityScope | None]:
    """Bind trusted effective authority for one asynchronous invocation."""
    return _CURRENT_SCOPE.set(scope)


def get_capability_scope() -> CapabilityScope | None:
    """Return current trusted authority, or ``None`` outside an invocation."""
    return _CURRENT_SCOPE.get()


def reset_capability_scope(token: Token[CapabilityScope | None]) -> None:
    """Restore the prior authority after success, failure, or cancellation."""
    _CURRENT_SCOPE.reset(token)


__all__ = [
    "bind_capability_scope", "get_capability_scope", "reset_capability_scope",
]

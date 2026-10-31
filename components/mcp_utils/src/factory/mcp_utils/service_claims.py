"""Opaque, exact-wrapper claims for protected in-process dispatch."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .service_bindings import InvocationBinding

_AUTHORITY = object()


@dataclass(frozen=True, slots=True, init=False)
class InternalInvocationClaims:
    """Authority for one exact wrapper and one operation binding."""

    caller: str
    audience: str
    target_tool: str
    binding: InvocationBinding
    _target: Any = field(repr=False)
    _permit: object = field(repr=False)

    def __init__(
        self, caller: str, audience: str, target_tool: str,
        binding: InvocationBinding, target: Any, *, authority: object,
    ) -> None:
        if authority is not _AUTHORITY:
            raise TypeError("internal invocation claims must be minted")
        for name, value in (
            ("caller", caller), ("audience", audience),
            ("target_tool", target_tool),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        object.__setattr__(self, "caller", caller.strip())
        object.__setattr__(self, "audience", audience.strip())
        object.__setattr__(self, "target_tool", target_tool.strip())
        object.__setattr__(self, "binding", binding)
        object.__setattr__(self, "_target", getattr(target, "fn", target))
        object.__setattr__(self, "_permit", object())


def mint_internal_invocation_claims(
    *, caller: str, audience: str, target_tool: str,
    binding: InvocationBinding, target: Any,
) -> InternalInvocationClaims:
    """Mint a non-transport permit bound to the resolved wrapper object."""
    return InternalInvocationClaims(
        caller, audience, target_tool, binding, target, authority=_AUTHORITY,
    )


__all__ = ["InternalInvocationClaims", "mint_internal_invocation_claims"]

"""Fail-closed DCAL request permits; no production mint or ambient scope exists."""
from __future__ import annotations

from dataclasses import dataclass, field

from factory.blockchain.mcp.contracts.dcal.models import TrustedBinding


@dataclass(frozen=True, slots=True, init=False)
class TrustedEnvelope:
    """Opaque permit type reserved for a future authenticated gateway adapter."""

    binding: TrustedBinding
    _permit: object = field(repr=False)

    def __init__(self, *_: object, **__: object) -> None:
        raise TypeError("DCAL request permits require an authenticated gateway adapter")


def resolve_trusted_envelope(candidate: object | None = None) -> TrustedEnvelope | None:
    """Fail closed: DCAL has no production authority source until gateway integration."""
    del candidate
    return None


__all__ = ["TrustedEnvelope", "resolve_trusted_envelope"]

"""Port for mutable, encrypted, generation-fenced credential slots.

Distinct from the immutable content-addressed protected-artifact store: slots
hold rotatable durable secrets (client secrets, refresh tokens) at rest as
ciphertext, keyed by an owner/tenant/provider/connection/slot-kind identity,
with a generation fence and an optimistic-concurrency version.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

_SLOT_KINDS = frozenset({"client_secret", "refresh_token"})


class CredentialSlotError(ValueError):
    """Opaque denial for missing, foreign, tampered, tombstoned, or stale slots."""


@dataclass(frozen=True, slots=True)
class SlotIdentity:
    """The exact owner/tenant/provider/connection/kind coordinate of one slot."""
    tenant_id: str
    owner_id: str
    provider_id: str
    connection_ref: str
    slot_kind: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "provider_id", "connection_ref"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise CredentialSlotError("credential slot unavailable")
        if self.slot_kind not in _SLOT_KINDS:
            raise CredentialSlotError("credential slot unavailable")


@dataclass(frozen=True, slots=True)
class SlotReceipt:
    """Non-secret outcome of a slot mutation."""
    generation: int
    version: int


@dataclass(frozen=True, slots=True)
class DecryptedSlot:
    """Plaintext secret material — only ever handed to the auth broker in-process."""
    secret: dict[str, Any]
    generation: int
    version: int


class CredentialSlotStore(Protocol):
    """Encrypted, mutable, generation-fenced credential slots with fenced CAS."""

    def write(
        self, identity: SlotIdentity, secret: Mapping[str, Any], *,
        generation: int, expected_version: int | None,
    ) -> SlotReceipt:
        """Create (expected_version None) or rotate (fenced CAS on version)."""
        ...

    def read(self, identity: SlotIdentity, *, generation: int) -> DecryptedSlot:
        """Return the decrypted secret bound to this exact generation."""
        ...

    def revoke(self, identity: SlotIdentity, *, generation: int) -> SlotReceipt:
        """Bump the generation fence and tombstone, invalidating prior authority."""
        ...

    def rekey(self, identity: SlotIdentity, *, generation: int) -> SlotReceipt:
        """Re-wrap the same plaintext under the active KEK; no plaintext change."""
        ...


__all__ = [
    "CredentialSlotError", "CredentialSlotStore", "DecryptedSlot",
    "SlotIdentity", "SlotReceipt",
]

"""Port for owner-managed, arbitrary-named, write-only-back secrets.

Distinct from ``credential_slots``: this is a public, owner-facing "store my
own API key/secret under a name I choose" surface (Settings -> Secrets), not
an internal OAuth-egress coordinate. There is no second authorization
authority to broker and no generation fence — the owner manages their own
secrets and never reads them back, so this is a plain last-write-wins named
KV, encrypted at rest, scoped to (tenant_id, principal_id).

There is NO read/reveal method on this port, by design — matching upstream's
own write-only-back posture. Values exist in memory only around set().
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class OwnerSecretError(ValueError):
    """Opaque denial for missing, foreign, tampered, or malformed secrets."""

    def __init__(self) -> None:
        super().__init__("owner secret unavailable")


@dataclass(frozen=True, slots=True)
class OwnerSecretIdentity:
    """The exact tenant/principal coordinate a secret name is scoped under."""
    tenant_id: str
    principal_id: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "principal_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise OwnerSecretError()


class OwnerSecretStore(Protocol):
    """Encrypted, mutable, owner-named secret KV. No read/reveal method."""

    def set_secret(self, ident: OwnerSecretIdentity, name: str, value: str) -> None:
        """Create or overwrite the secret at ``name`` (last-write-wins)."""
        ...

    def delete_secret(self, ident: OwnerSecretIdentity, name: str) -> bool:
        """Remove the secret at ``name``. Returns True iff it existed."""
        ...

    def list_names(self, ident: OwnerSecretIdentity) -> list[str]:
        """Return the caller's own stored secret names — never values."""
        ...


__all__ = ["OwnerSecretError", "OwnerSecretIdentity", "OwnerSecretStore"]

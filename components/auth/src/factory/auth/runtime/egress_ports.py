"""Ports for the tokenless credential-injecting egress broker.

- ``SecretStorePort`` reads/writes durable secrets as opaque dicts through the
  storage credential-slot service (tokens/secrets are never returned to callers
  outside auth's own broker call stack).
- ``TokenAcquirer`` turns a durable secret into a short-lived access token
  (delegated or client-credentials flow). Access tokens live only here.
- ``ProviderEgress`` performs one route call with the injected token and returns
  a status + a sanitized business result — never the token.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .egress_models import ProviderRoute, SlotCoordinate


@dataclass(frozen=True, slots=True)
class SlotOutcome:
    generation: int
    version: int


@dataclass(frozen=True, slots=True)
class AcquiredToken:
    """A short-lived access token plus optional rotated durable secret."""
    access_token: str
    expires_at: float
    rotated_secret: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class SecretRead:
    """A decrypted durable secret plus its live generation and version."""
    secret: dict[str, Any]
    generation: int
    version: int


class SecretStorePort(Protocol):
    def write(self, coord: SlotCoordinate, secret: Mapping[str, Any], *,
              generation: int, expected_version: int | None) -> SlotOutcome | None: ...

    def read(self, coord: SlotCoordinate, *, generation: int) -> "SecretRead | None": ...

    def revoke(self, coord: SlotCoordinate, *, generation: int) -> SlotOutcome | None: ...


class TokenAcquirer(Protocol):
    def acquire(self, route: ProviderRoute, secret: Mapping[str, Any], *,
                force_refresh: bool) -> AcquiredToken | None: ...


class ProviderEgress(Protocol):
    def call(self, route: ProviderRoute, access_token: str,
             payload: Mapping[str, Any]) -> tuple[str, dict[str, Any]]: ...


__all__ = [
    "AcquiredToken", "ProviderEgress", "SecretRead", "SecretStorePort",
    "SlotOutcome", "TokenAcquirer",
]

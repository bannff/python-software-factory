"""Single-use enrollment state + PKCE for the OAuth authorization-code flow.

The ``state`` is the server-minted CSRF/identity anchor: the owner/tenant and the
PKCE ``code_verifier`` are captured at begin-time (under the authenticated
envelope) and looked up at callback-time, so the browser redirect (which carries
no bearer) is bound to the principal without trusting the redirect itself. The
verifier NEVER leaves the server. State is single-use and TTL-bounded.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

_TTL_SECONDS = 600.0


def new_state() -> str:
    return secrets.token_urlsafe(32)


def new_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


@dataclass(frozen=True, slots=True)
class EnrollmentRecord:
    provider_id: str
    connection_ref: str
    owner_id: str
    tenant_id: str
    redirect_uri: str
    code_verifier: str
    created_at: float


class EnrollmentStateStore(Protocol):
    def put(self, state: str, record: EnrollmentRecord) -> None: ...
    def take(self, state: str) -> EnrollmentRecord | None: ...


class InMemoryEnrollmentStateStore:
    """Process-local, single-use, TTL-bounded state store."""

    def __init__(self, *, clock=time.time) -> None:
        self._clock = clock
        self._records: dict[str, EnrollmentRecord] = {}
        self._lock = Lock()

    def put(self, state: str, record: EnrollmentRecord) -> None:
        with self._lock:
            self._prune()
            self._records[state] = record

    def take(self, state: str) -> EnrollmentRecord | None:
        with self._lock:
            self._prune()
            record = self._records.pop(state, None)
        if record is None:
            return None
        if self._clock() - record.created_at > _TTL_SECONDS:
            return None
        return record

    def _prune(self) -> None:
        cutoff = self._clock() - _TTL_SECONDS
        stale = [s for s, r in self._records.items() if r.created_at < cutoff]
        for s in stale:
            self._records.pop(s, None)


__all__ = [
    "EnrollmentRecord", "EnrollmentStateStore", "InMemoryEnrollmentStateStore",
    "new_pkce", "new_state",
]

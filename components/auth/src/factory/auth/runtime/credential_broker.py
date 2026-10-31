"""Tokenless credential-injecting egress broker.

Owns the access-token cache (in-memory only — tokens are never persisted and
never returned across MCP), per-connection refresh single-flight, one bounded
401 retry, and revocation that bumps the storage generation fence and evicts
the cache. Durable secrets are read through ``SecretStorePort`` (storage
credential slots). This broker performs no provider network I/O itself; that is
delegated to injected provider adapters (FAKE in this foundation).
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Any, Mapping

from factory.mcp_utils.interface import sanitize_protected

from .egress_models import EgressResult, ProviderRoute, SlotCoordinate, redact_secrets
from .egress_ports import AcquiredToken, SecretStorePort

_Key = tuple[str, str, str, str]


class CredentialBroker:
    """Resolve a durable secret → short-lived token → sanitized egress result."""

    def __init__(self, secret_store: SecretStorePort,
                 providers: Mapping[str, Any], *, clock: Any = time.time) -> None:
        self._secret_store = secret_store
        self._providers = dict(providers)
        self._clock = clock
        self._tokens: dict[_Key, tuple[int, AcquiredToken]] = {}
        self._generations: dict[_Key, int] = {}
        self._locks: dict[_Key, Lock] = {}
        self._map_lock = Lock()

    @staticmethod
    def _key(coord: SlotCoordinate) -> _Key:
        return (coord.tenant_id, coord.owner_id, coord.provider_id, coord.connection_ref)

    def _lock_for(self, key: _Key) -> Lock:
        with self._map_lock:
            return self._locks.setdefault(key, Lock())

    def enroll(self, coord: SlotCoordinate, secret: Mapping[str, Any]) -> int | None:
        """Seed the durable secret at generation 1; return the live generation."""
        outcome = self._secret_store.write(
            coord, secret, generation=1, expected_version=None)
        if outcome is None:
            return None
        with self._map_lock:
            self._generations[self._key(coord)] = outcome.generation
        return outcome.generation

    def revoke(self, coord: SlotCoordinate) -> bool:
        """Bump the generation fence, then evict the cached token.

        Holds the per-key lock so an in-flight refresh cannot repopulate the
        cache after eviction (closes the revoke/acquire TOCTOU).
        """
        key = self._key(coord)
        with self._lock_for(key):
            generation = self._generations.get(key)
            if generation is None:
                return False
            outcome = self._secret_store.revoke(coord, generation=generation)
            with self._map_lock:
                self._generations[key] = outcome.generation if outcome else generation + 1
            self._tokens.pop(key, None)
            return outcome is not None

    def egress(self, coord: SlotCoordinate, route: ProviderRoute,
               payload: Mapping[str, Any]) -> EgressResult:
        """Inject a broker-held token into one route call; at most one 401 retry."""
        provider = self._providers.get(coord.provider_id)
        if provider is None:
            return EgressResult(status="denied")
        token = self._token(coord, route, provider, force=False)
        if token is None:
            return EgressResult(status="unauthorized")
        status, result = provider.call(route, token, dict(payload))
        if status == "unauthorized":
            token = self._token(coord, route, provider, force=True)
            if token is None:
                return EgressResult(status="unauthorized")
            status, result = provider.call(route, token, dict(payload))
        if status != "ok":
            return EgressResult(status="unauthorized" if status == "unauthorized" else "denied")
        return EgressResult(status="ok", result=redact_secrets(sanitize_protected(result)))

    def _token(self, coord: SlotCoordinate, route: ProviderRoute,
               provider: Any, *, force: bool) -> str | None:
        key = self._key(coord)
        with self._lock_for(key):
            generation = self._generations.get(key)
            if generation is None:
                return None
            if not force:
                cached = self._tokens.get(key)
                # a cache hit is honored only at the current generation fence
                if cached is not None and cached[0] == generation \
                        and cached[1].expires_at > self._clock():
                    return cached[1].access_token
            read = self._secret_store.read(coord, generation=generation)
            if read is None:
                self._tokens.pop(key, None)  # revoked/tombstoned invalidates the cache
                return None
            acquired = provider.acquire(route, read.secret, force_refresh=force)
            if acquired is None:
                return None
            if acquired.rotated_secret is not None:
                self._secret_store.write(
                    coord, acquired.rotated_secret,
                    generation=generation, expected_version=read.version)
            self._tokens[key] = (generation, acquired)
            return acquired.access_token


__all__ = ["CredentialBroker"]

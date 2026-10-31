"""Bounded, context-scoped idempotency replay for typed MCP egress."""
from __future__ import annotations

import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Event, RLock
from typing import Any

from factory.mcp_utils.runtime.tool_result import ToolResult, with_idempotency_key
from .bounded_json import to_plain_json
from .idempotency_identity import ReplayIdentity, build_identity

_TTL_SECONDS = 300.0
_MAX_ENTRIES = 1024
_MAX_BYTES = 16 * 1024 * 1024
_WAIT_SECONDS = 30.0
_FLIGHT_TTL_SECONDS = 2 * _WAIT_SECONDS

_LOCK = RLock()
_CACHE: OrderedDict[tuple[str, str, str], _Entry] = OrderedDict()
_INFLIGHT: dict[tuple[str, str, str], _Flight] = {}
_CACHE_BYTES = 0


@dataclass
class _Entry:
    payload: dict[str, Any]
    input_digest: str | None
    expires_at: float
    size_bytes: int


@dataclass
class _Flight:
    identity: ReplayIdentity
    event: Event
    result: ToolResult[Any] | None = None
    claimed_at: float = field(default_factory=time.monotonic)


@dataclass(frozen=True)
class ReplayDecision:
    action: str
    result: ToolResult[Any] | None = None
    flight: _Flight | None = None


def _flight_failure(flight: _Flight) -> ToolResult[Any]:
    return with_idempotency_key(
        ToolResult(ok=False, error="tool_execution_failed"), flight.identity.key,
    )


def lookup_or_claim(identity: ReplayIdentity | None) -> ReplayDecision:
    """Atomically return a hit, conflict, waiter, or the sole execution claim."""
    if identity is None:
        return ReplayDecision("disabled")
    cache_key = _cache_key(identity)
    with _LOCK:
        _purge_locked()
        entry = _CACHE.get(cache_key)
        if entry is not None:
            if entry.input_digest != identity.input_digest:
                return ReplayDecision("conflict")
            _CACHE.move_to_end(cache_key)
            return ReplayDecision("hit", ToolResult.model_validate(entry.payload))
        flight = _INFLIGHT.get(cache_key)
        if flight is not None:
            return ReplayDecision(
                "wait" if flight.identity.input_digest == identity.input_digest else "conflict",
                flight=flight if flight.identity.input_digest == identity.input_digest else None,
            )
        flight = _Flight(identity, Event())
        _INFLIGHT[cache_key] = flight
        return ReplayDecision("owner", flight=flight)


def wait_for(flight: _Flight) -> ToolResult[Any]:
    """Wait outside the cache lock; async callers should use ``asyncio.to_thread``."""
    if not flight.event.wait(_WAIT_SECONDS):
        return _flight_failure(flight)
    return flight.result or _flight_failure(flight)


def complete(flight: _Flight, result: ToolResult[Any]) -> ToolResult[Any]:
    """Publish an owner result and wake waiters; stale owners cannot overwrite."""
    result = with_idempotency_key(result, flight.identity.key)
    cache_key = _cache_key(flight.identity)
    with _LOCK:
        if _INFLIGHT.get(cache_key) is not flight:
            return result
        del _INFLIGHT[cache_key]
        try:
            if result.ok and not _store_locked(flight.identity, result):
                result = _flight_failure(flight)
        except Exception:
            result = _flight_failure(flight)
        finally:
            flight.result = result
            flight.event.set()
        return result


def cache_get(
    scope: str, key: str, input_digest: str | None = None,
    context_digest: str = "",
) -> ToolResult[Any] | None:
    """Return a matching cached result, retaining the legacy test/helper API."""
    if not key:
        return None
    with _LOCK:
        _purge_locked()
        entry = _CACHE.get((scope, key, context_digest))
        if entry is None or (input_digest is not None and entry.input_digest != input_digest):
            return None
        _CACHE.move_to_end((scope, key, context_digest))
        return ToolResult.model_validate(entry.payload)


def cache_put(
    scope: str, key: str, result: ToolResult[Any], input_digest: str | None = None,
    context_digest: str = "",
) -> None:
    """Cache a successful result under bounded replay limits."""
    if not key or not result.ok:
        return
    stamped = with_idempotency_key(result, key)
    with _LOCK:
        _store_locked(
            ReplayIdentity(scope, key, context_digest, input_digest or ""), stamped,
        )


def cache_clear() -> None:
    """Drop completed entries and release current waiters without stale writes."""
    global _CACHE_BYTES
    with _LOCK:
        for flight in _INFLIGHT.values():
            flight.result = _flight_failure(flight)
            flight.event.set()
        _INFLIGHT.clear()
        _CACHE.clear()
        _CACHE_BYTES = 0


def cache_size() -> int:
    with _LOCK:
        _purge_locked()
        return len(_CACHE)


def _cache_key(identity: ReplayIdentity) -> tuple[str, str, str]:
    return identity.scope, identity.key, identity.context_digest


def _purge_locked() -> None:
    global _CACHE_BYTES
    now = time.monotonic()
    for key, entry in list(_CACHE.items()):
        if entry.expires_at <= now:
            _CACHE.pop(key, None)
            _CACHE_BYTES -= entry.size_bytes
    for key, flight in list(_INFLIGHT.items()):
        if flight.claimed_at + _FLIGHT_TTL_SECONDS <= now:
            _INFLIGHT.pop(key, None)
            flight.result = _flight_failure(flight)
            flight.event.set()


def _store_locked(identity: ReplayIdentity, result: ToolResult[Any]) -> bool:
    global _CACHE_BYTES
    payload = to_plain_json(result.model_dump(mode="python"))
    try:
        encoded = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return False
    if len(encoded) > _MAX_BYTES:
        return False
    key = _cache_key(identity)
    old = _CACHE.pop(key, None)
    if old is not None:
        _CACHE_BYTES -= old.size_bytes
    _CACHE[key] = _Entry(payload, identity.input_digest, time.monotonic() + _TTL_SECONDS, len(encoded))
    _CACHE_BYTES += len(encoded)
    while len(_CACHE) > _MAX_ENTRIES or _CACHE_BYTES > _MAX_BYTES:
        _, evicted = _CACHE.popitem(last=False)
        _CACHE_BYTES -= evicted.size_bytes
    return True


__all__ = [
    "ReplayDecision", "ReplayIdentity", "build_identity", "cache_clear",
    "cache_get", "cache_put", "cache_size", "complete", "lookup_or_claim",
    "wait_for",
]

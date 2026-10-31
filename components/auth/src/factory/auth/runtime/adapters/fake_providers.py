"""In-memory FAKE provider adapters (no network).

Prove the tokenless egress path end-to-end for two provider families:
- Microsoft delegated: refreshes an access token from a durable refresh token.
- Adobe client-credentials: exchanges a durable client secret for a token.

Real Graph/Adobe network calls belong to child stories. These fakes derive a
deterministic token from the secret, count acquisitions (so single-flight is
observable), and can simulate one 401 to exercise the bounded retry.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Mapping

from ..egress_models import ProviderRoute
from ..egress_ports import AcquiredToken


class FakeProvider:
    """A single provider family implementing TokenAcquirer + ProviderEgress."""

    def __init__(self, *, unauthorized_first: bool = False,
                 rotate_on_refresh: bool = False, ttl_s: float = 3600.0,
                 clock: Any = time.time) -> None:
        self._unauthorized_first = unauthorized_first
        self._rotate_on_refresh = rotate_on_refresh
        self._ttl_s = ttl_s
        self._clock = clock
        self.acquire_calls = 0
        self.call_count = 0

    def acquire(self, route: ProviderRoute, secret: Mapping[str, Any], *,
                force_refresh: bool) -> AcquiredToken | None:
        self.acquire_calls += 1
        material = secret.get(route.secret_slot_kind)
        if not isinstance(material, str) or not material:
            return None
        seed = f"{route.provider_id}:{route.route_id}:{material}:{self.acquire_calls}"
        access = "fat_" + hashlib.sha256(seed.encode()).hexdigest()
        rotated = None
        if self._rotate_on_refresh and force_refresh:
            rotated = {route.secret_slot_kind: "rot_" + hashlib.sha256(
                (material + "next").encode()).hexdigest()}
        return AcquiredToken(
            access_token=access, expires_at=self._clock() + self._ttl_s,
            rotated_secret=rotated)

    def call(self, route: ProviderRoute, access_token: str,
             payload: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        self.call_count += 1
        if self._unauthorized_first and self.call_count == 1:
            return "unauthorized", {}
        echo = {key: payload[key] for key in route.allowed_fields if key in payload}
        return "ok", {"provider_id": route.provider_id, "route_id": route.route_id, "echo": echo}


def default_fake_providers() -> dict[str, FakeProvider]:
    """One fake per shipped provider family."""
    return {"microsoft": FakeProvider(), "adobe": FakeProvider()}


__all__ = ["FakeProvider", "default_fake_providers"]

"""Env-driven DNS-rebinding allowlist for the streamable-HTTP transport.

The MCP SDK auto-enables Host-header (DNS-rebinding) protection for localhost
with a fixed allowlist, so a container dialing the server by its docker service
name (``companionx:8000``) or ``host.docker.internal`` gets a 421. This resolver
lets an operator *extend* the allowlist for a trusted container network without
losing the localhost defaults — protection stays on.

``MCP_ALLOWED_HOSTS`` is a comma-separated list of Host values (the SDK's
``name:*`` port-wildcard is supported). The sentinel ``*`` disables rebinding
protection entirely (trusted network, explicit opt-out). Unset ⇒ ``None`` ⇒
byte-identical legacy behavior (SDK localhost auto-protection).
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_LOCALHOST_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
_LOCALHOST_ORIGINS = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]


def _dedupe(items: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return list(seen)


def _origins_for(host: str) -> list[str]:
    return [f"http://{host}", f"https://{host}"]


def resolve_transport_security(env: dict[str, str] | None = None) -> Any | None:
    """Build ``TransportSecuritySettings`` from ``MCP_ALLOWED_HOSTS``.

    Returns ``None`` when the env var is unset, deferring to the SDK default.
    """
    source = env if env is not None else os.environ
    raw = (source.get("MCP_ALLOWED_HOSTS") or "").strip()
    if not raw:
        return None

    from mcp.server.transport_security import TransportSecuritySettings

    if raw == "*":
        logger.warning(
            "MCP_ALLOWED_HOSTS='*' — DNS-rebinding (Host-header) protection is "
            "DISABLED. Only safe on a trusted, non-public network.",
        )
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)

    extra = [host.strip() for host in raw.split(",") if host.strip()]
    extra_origins = [origin for host in extra for origin in _origins_for(host)]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_dedupe(_LOCALHOST_HOSTS + extra),
        allowed_origins=_dedupe(_LOCALHOST_ORIGINS + extra_origins),
    )


__all__ = ["resolve_transport_security"]

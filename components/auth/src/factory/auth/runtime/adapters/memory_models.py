"""Data models for the in-memory authentication backend.

These dataclasses store user and token information for the MemoryBackend.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StoredUser:
    """User stored in memory backend."""
    subject: str
    username: str
    email: str | None = None
    tenant_id: str | None = None
    scopes: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)


@dataclass
class StoredToken:
    """Token stored in memory backend."""
    token: str
    subject: str
    expires_at: float
    scopes: list[str] = field(default_factory=list)
    audience: str | None = None
    refresh_token: str | None = None
    revoked: bool = False

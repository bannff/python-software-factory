"""In-memory sandbox environment store.

Zero-dependency store for local dev and testing.
"""

from __future__ import annotations

from typing import Any

from ..models import EnvironmentInfo


class MemorySandboxStore:
    """In-memory sandbox environment persistence."""

    def __init__(self) -> None:
        self._envs: dict[str, EnvironmentInfo] = {}

    def save(self, env: EnvironmentInfo) -> None:
        self._envs[env.env_id] = env

    def load(self, env_id: str) -> EnvironmentInfo | None:
        return self._envs.get(env_id)

    def list_environments(self, status: str | None = None) -> list[EnvironmentInfo]:
        envs = list(self._envs.values())
        if status:
            envs = [e for e in envs if e.status == status]
        return envs

    def delete(self, env_id: str) -> bool:
        return self._envs.pop(env_id, None) is not None

    def health_check(self) -> dict[str, Any]:
        return {
            "healthy": True,
            "backend": "memory",
            "environment_count": len(self._envs),
        }

"""Runtime-owned authorization policy for machine-learning authoring actions."""
from __future__ import annotations

import os

_ENV = "ML_ENABLE_AUTHORING_TOOLS"
_TRUE = frozenset({"1", "true", "yes", "y", "on"})


def authoring_enabled() -> bool:
    """Return whether privileged artifact acquisition/configuration is enabled."""
    return os.environ.get(_ENV, "").strip().lower() in _TRUE


def require_authoring() -> None:
    """Fail before importing an SDK or touching a remote service when disabled."""
    if not authoring_enabled():
        raise PermissionError(f"Authoring tools disabled. Set {_ENV}=1")


__all__ = ["authoring_enabled", "require_authoring"]

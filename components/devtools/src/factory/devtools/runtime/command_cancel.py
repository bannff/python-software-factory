"""Process-local cancellation handles for active project commands."""
from __future__ import annotations

import threading

from .models import ProjectBinding

_LOCK = threading.Lock()
_ACTIVE: dict[str, tuple[str, str, str, threading.Event]] = {}


def register(
    run_id: str, binding: ProjectBinding, event: threading.Event,
) -> None:
    with _LOCK:
        if run_id in _ACTIVE:
            raise RuntimeError("duplicate command run identity")
        _ACTIVE[run_id] = (
            binding.tenant_id, binding.owner_id, binding.session_id, event,
        )


def unregister(run_id: str) -> None:
    with _LOCK:
        _ACTIVE.pop(run_id, None)


def cancel(binding: ProjectBinding, run_id: str) -> bool:
    with _LOCK:
        value = _ACTIVE.get(run_id)
        if value is None or value[:3] != (
            binding.tenant_id, binding.owner_id, binding.session_id,
        ):
            return False
        value[3].set()
        return True


__all__ = ["cancel", "register", "unregister"]

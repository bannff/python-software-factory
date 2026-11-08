"""Typed refusal for work against unknown or terminated sandbox environments."""
from __future__ import annotations

from typing import TYPE_CHECKING

from factory.mcp_utils.interface import TypedToolFailure

from ..runtime.models import EnvironmentStatus

if TYPE_CHECKING:
    from ..runtime.runtime import SandboxRuntime


def require_live(runtime: "SandboxRuntime", env_id: str) -> None:
    """Raise a typed failure unless ``env_id`` is a known, non-terminated env."""
    status = runtime.stored_status(env_id)
    if status is None:
        raise TypedToolFailure("env_not_found", env_id)
    if status == EnvironmentStatus.TERMINATED:
        raise TypedToolFailure("environment_terminated", env_id)

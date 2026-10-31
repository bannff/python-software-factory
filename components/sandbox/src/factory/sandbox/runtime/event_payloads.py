"""Shared sandbox event-payload builders.

Every ``SandboxRuntime`` method emits an event whose payload starts with the
same environment-identity fields (``env_id``, ``entity_id`` and the
metadata-derived ``run_id``/``profile``/``target_app``). Centralizing that
shape here keeps the runtime methods DRY and guarantees a single, stable event
schema across the whole brick.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .models import EnvironmentInfo


class ContainerReapedPayload(BaseModel):
    """Typed payload for ``sandbox.container_reaped`` (orphan-sweep path only).

    Emitted when the host-owned orphan sweep reaps a workload container.
    ``policy_id`` is the verbatim ``MCP_POLICY_ID`` (``workload:<launch-id>``) —
    the single authoritative key Workflow uses to revoke the launch's scoped
    capability. Sandbox reports the fact; Workflow owns revocation. Never
    emitted on the graceful ``terminate`` path.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    policy_id: str
    env_id: str
    reason: Literal["exited", "dead"]
    reaped_at: str


def entity_id(env_id: str) -> str:
    """Return the canonical graph entity id for a sandbox environment."""
    return f"sandbox-env-{env_id}"


def base_env_payload(env_id: str, env: EnvironmentInfo | None) -> dict[str, Any]:
    """Identity fields common to command/file activity events.

    Tolerates a missing ``env`` (store miss) by emitting ``None`` for the
    metadata-derived fields, matching the pre-refactor behavior.
    """
    metadata = env.metadata if env is not None else {}
    return {
        "env_id": env_id,
        "entity_id": entity_id(env_id),
        "run_id": metadata.get("run_id"),
        "profile": metadata.get("profile"),
        "target_app": metadata.get("target_app"),
    }


def lifecycle_payload(env: EnvironmentInfo) -> dict[str, Any]:
    """Full identity + status payload for provision/terminate/status events."""
    return {
        "env_id": env.env_id,
        "entity_id": entity_id(env.env_id),
        "status": env.status.value,
        "instance_type": env.instance_type,
        "profile": env.metadata.get("profile"),
        "run_id": env.metadata.get("run_id"),
        "target_app": env.metadata.get("target_app"),
    }

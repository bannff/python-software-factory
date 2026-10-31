"""Orphan-container sweep + reap-event emission for the sandbox runtime.

The host-owned orphan sweep reaps crashed/exited containers. For workload
containers (labeled ``factory.workload=<policy_id>``) it emits
``sandbox.container_reaped`` so Workflow — the sole owner of credential
revocation — can revoke the launch's scoped capability. Sandbox only REPORTS
that a container is gone; it never revokes or decides revocation. The graceful
``terminate`` path is untouched (Workflow already owns it), so no reap event is
emitted there.

Lives as a mixin (mirroring ``CfnStackOpsMixin``) to keep ``runtime.py`` under
the per-file LOC ceiling and focused on environment lifecycle.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from .event_emitter import emit
from .event_payloads import ContainerReapedPayload
from .ports import SandboxPort


class _HasAdapter(Protocol):
    _adapter: SandboxPort


class OrphanSweepMixin:
    """Sweep reaped orphans and emit reap events, mixed into ``SandboxRuntime``."""

    def sweep_orphans(self: _HasAdapter) -> list[dict[str, Any]]:
        """Reap crashed/exited containers; emit one reap event per workload.

        Returns the reaped list ``[{container_id, policy_id, reason}]``. Only
        containers carrying a ``policy_id`` (workloads) emit
        ``sandbox.container_reaped``; unlabeled orphans are reaped silently.
        Adapters without a sweep seam (mock/AWS) are a no-op.
        """
        sweep = getattr(self._adapter, "sweep_orphans", None)
        if sweep is None:
            return []
        reaped: list[dict[str, Any]] = sweep()
        reaped_at = datetime.now(timezone.utc).isoformat()
        for item in reaped:
            policy_id = item.get("policy_id")
            if not policy_id:
                continue
            payload = ContainerReapedPayload(
                policy_id=policy_id,
                env_id=item.get("container_id", ""),
                reason=item.get("reason", "exited"),
                reaped_at=reaped_at,
            )
            emit("sandbox.container_reaped", payload.model_dump())
        return reaped

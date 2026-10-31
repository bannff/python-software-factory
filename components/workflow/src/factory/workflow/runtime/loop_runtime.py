"""Workflow runtime mixin for durable goal and monitor loops."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .envelope import Envelope, FrozenEnvelope
from .loop_admission import admit_pending
from .loop_lifecycle import LoopLifecycle
from .loop_models import LoopKind, LoopRecord, LoopState
from .loop_reconcile import reconcile_cycles


class LoopRuntime:
    def _loop_store(self) -> Any:
        required = ("create_loop", "list_cycles", "settle_cycle")
        if not all(hasattr(self.storage, name) for name in required):
            raise RuntimeError("durable loops require SQLite Workflow storage")
        return self.storage

    def start_loop(
        self, *, kind: str, agent_id: str, objective: str, cycle_instructions: str,
        interval_seconds: int, max_cycles: int, max_runtime_seconds: int,
        loop_id: str | None, origin_session_id: str, envelope: Envelope,
    ) -> LoopRecord:
        tenant, owner, thread = _identity(envelope)
        if not thread:
            raise ValueError("loop_session_context_required")
        project, _ = self._loop_roots()
        now = datetime.now(timezone.utc)
        deadline = (now + timedelta(seconds=max_runtime_seconds)
                    if max_runtime_seconds else None)
        record = LoopRecord(
            tenant_id=tenant, owner_id=owner,
            loop_id=loop_id or f"lp_{uuid4().hex}",
            origin_session_id=origin_session_id, origin_thread_id=thread,
            agent_id=agent_id, kind=LoopKind(kind),
            objective=objective, cycle_instructions=cycle_instructions,
            interval_seconds=interval_seconds, max_cycles=max_cycles,
            runtime_deadline=deadline, project_root=str(project),
            project_root_digest=hashlib.sha256(str(project).encode()).hexdigest(),
            created_at=now, updated_at=now,
            initiation_envelope=FrozenEnvelope.model_validate(envelope.model_dump()),
        )
        return LoopLifecycle(self._loop_store()).start(record)[0]

    def get_loop(self, loop_id: str, envelope: Envelope) -> LoopRecord:
        tenant, owner, _ = _identity(envelope)
        record = self._loop_store().get_loop(tenant, owner, loop_id)
        if record is None:
            raise ValueError("loop_not_found")
        return record

    def list_loops(self, envelope: Envelope, limit: int = 100) -> list[LoopRecord]:
        tenant, owner, _ = _identity(envelope)
        return self._loop_store().list_loops(tenant, owner, limit)

    def get_loop_cycle(
        self, loop_id: str, cycle: int, envelope: Envelope,
    ):
        loop = self.get_loop(loop_id, envelope)
        record = self._loop_store().get_cycle(
            loop.tenant_id, loop.owner_id, loop.loop_id, cycle,
        )
        if record is None:
            raise ValueError("loop_cycle_not_found")
        return record

    def transition_loop(
        self, loop_id: str, expected_revision: int,
        state: LoopState, envelope: Envelope,
    ) -> LoopRecord:
        record = self.get_loop(loop_id, envelope)
        reason = "user_stop" if state is LoopState.STOPPED else None
        return LoopLifecycle(self._loop_store()).transition(
            record, state, expected_revision, reason,
        )

    async def reconcile_loops(self, limit: int = 100) -> tuple[str, ...]:
        project, allowed = self._loop_roots()
        store = self._loop_store()
        settled = await reconcile_cycles(store, allowed, limit)
        admitted = await admit_pending(store, allowed, limit)
        return (*settled, *admitted)

    @staticmethod
    def _loop_roots() -> tuple[Path, Path]:
        project = Path(os.getenv("COMPANION_X_PROJECT_ROOT", os.getcwd())).resolve(strict=True)
        allowed = Path(os.getenv("COMPANION_X_WORKSPACE_ROOT", str(project))).resolve(strict=True)
        try:
            project.relative_to(allowed)
        except ValueError as exc:
            raise RuntimeError("loop project root is not allowed") from exc
        return project, allowed


def _identity(envelope: Envelope) -> tuple[str, str, str | None]:
    """Resolve (tenant, owner, session) from the ambient envelope.

    Only ``tenant_id``/``principal_id`` are required here — every read path
    (``get_loop``/``list_loops``/``get_loop_cycle``/``transition_loop``)
    discards the session value entirely; only ``start_loop`` actually
    consumes it (as ``origin_thread_id``), and validates its presence
    itself. A page-level dashboard call (no active chat turn) legitimately
    carries no session id and must still be able to list/read/pause/resume/
    stop loops it owns.
    """
    tenant, principal, session = envelope.tenant_id, envelope.principal_id, envelope.session_id
    if not (isinstance(tenant, str) and tenant) or not (isinstance(principal, str) and principal):
        raise ValueError("loop_owner_context_required")
    return tenant, principal, session if isinstance(session, str) and session else None


__all__ = ["LoopRuntime"]

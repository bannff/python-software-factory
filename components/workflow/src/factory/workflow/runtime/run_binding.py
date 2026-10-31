"""Deterministic identity verification for persisted durable workflow runs."""
from __future__ import annotations

from typing import Any

from .task_ids import workflow_run_id


class DurableIntegrityError(ValueError):
    """Persisted durable authority no longer matches its canonical binding."""


class DurableRunBindingError(DurableIntegrityError):
    """Persisted durable run identity no longer matches its canonical input."""


class DurableAttemptBindingError(DurableIntegrityError):
    """Persisted task attempt no longer matches its deterministic arguments."""


def verify_durable_run_binding(run: Any) -> None:
    """Recompute and verify both durable run and execution identities."""
    version_id = getattr(run, "workflow_version_id", None)
    if version_id is None:
        return
    run_key = getattr(run, "run_key", None)
    if not isinstance(run_key, str) or not run_key.strip():
        raise DurableRunBindingError("durable run binding requires a non-empty run_key")
    expected = workflow_run_id(version_id, run_key, run.input)
    if run.run_id != expected:
        raise DurableRunBindingError("durable run_id does not match canonical run input")
    if run.run_execution_id != expected:
        raise DurableRunBindingError("durable run_execution_id does not match run identity")

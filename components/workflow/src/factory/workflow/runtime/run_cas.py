"""Observe-or-win helpers for revision-fenced workflow run transitions."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from .models import RunRecord
from .ports import WorkflowStorage

ACTIVE_STATUSES = frozenset({"pending", "running", "waiting"})
TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
RunFields = Callable[[RunRecord], dict[str, Any]]


def observe_or_transition(
    storage: WorkflowStorage, record: RunRecord, *, status: str,
    fields: RunFields,
) -> tuple[RunRecord, bool]:
    """Return a terminal winner or win one strict active-state CAS.

    ``fields`` is recomputed after every stale revision so callers preserve
    refreshed authoritative fields while retaining their transition intent.
    """
    current = record
    while True:
        if current.status in TERMINAL_STATUSES:
            return current, False
        if current.status not in ACTIVE_STATUSES:
            raise ValueError(f"unsupported run status: {current.status}")
        try:
            updated = storage.update_run(
                run_id=current.run_id, status=status,
                now=datetime.now(timezone.utc),
                expected_statuses=set(ACTIVE_STATUSES),
                expected_revision=current.revision, **fields(current),
            )
            return updated, True
        except ValueError as exc:
            if str(exc) != "stale run transition":
                raise
            refreshed = storage.get_run(run_id=current.run_id)
            if refreshed is None:
                raise RuntimeError("run disappeared after stale transition") from exc
            current = refreshed

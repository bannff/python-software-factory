"""Cockpit receipts for CAN lifecycle TRAIN terminals.

The lifecycle composition path reaches the tracker but never the
``ml_training_runs`` cockpit table (issue #80 phase 2 gap; the keystone
path already persists via :mod:`training_run_store`). This module mirrors
``build_run_record`` for portfolio rows — flat dicts, not job objects:
sealed model trees are the artifact authority in the lifecycle path.
Best-effort and idempotent (``mlrun-{job_id}`` doc ids), never fails a
terminal.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .adapters.training_run_store import _insert_record

logger = logging.getLogger(__name__)


def _portfolio_run_record(row: dict[str, Any], experiment_name: str) -> dict[str, Any]:
    """Serialize a lifecycle portfolio row into the canonical run record."""
    model_type = str(row.get("model_family", ""))
    return {
        "run_id": row.get("job_id"),
        "experiment_name": experiment_name or f"can-ts-{model_type}",
        "model_type": model_type,
        "status": "completed",
        "metrics": {
            k: v for k, v in dict(row.get("metrics") or {}).items()
            if isinstance(v, (int, float))
        },
        "config": row.get("training_config") or {},
        "model_path": row.get("model_path"),
        "source": "can_lifecycle",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def persist_portfolio_receipts(terminal: dict[str, Any]) -> None:
    """Persist cockpit receipts for a completed lifecycle TRAIN terminal."""
    if terminal.get("status") != "completed":
        return
    experiment_name = str(
        (terminal.get("evaluation_record_request") or {}).get("experiment_name", ""),
    )
    for row in terminal.get("portfolio") or []:
        run_id = row.get("job_id")
        if not run_id:
            continue
        try:
            record = _portfolio_run_record(row, experiment_name)
            if not _insert_record(record):
                logger.warning(
                    "can_lifecycle_receipts: receipt not persisted for %s",
                    run_id,
                )
        except Exception as exc:
            logger.warning(
                "can_lifecycle_receipts: receipt persist failed for %s: %s",
                run_id, exc,
            )


__all__ = ["persist_portfolio_receipts"]

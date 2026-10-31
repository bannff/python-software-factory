"""Restart reconciliation for nonterminal Session steer deliveries."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..models import SteerMessage, SteerState


def reconcile_written(
    sql: Any,
    transition: Callable[[str, str, str, str, SteerState, int], SteerMessage | None],
) -> list[SteerMessage]:
    """CAS every persisted written delivery to requeued exactly once."""
    rows = sql.fetch_all(
        "SELECT tenant_id, owner_id, session_id, delivery_id, revision "
        "FROM session_steers WHERE state='written' ORDER BY created_at, delivery_id",
    )
    recovered: list[SteerMessage] = []
    for row in rows:
        value = transition(
            row["tenant_id"], row["owner_id"], row["session_id"],
            row["delivery_id"], SteerState.REQUEUED, row["revision"],
        )
        if value is not None:
            recovered.append(value)
    return recovered


__all__ = ["reconcile_written"]

"""Steer-mailbox mixin for the SQL session store.

Split out of ``sql.py`` to keep that file under the 200 LOC ceiling — steer
delivery (append/get/list/transition/reconcile) is a genuinely separate
concern from session lifecycle mutations, same split rationale already
applied to the MCP-layer ``operational.py``/``steering.py`` this cycle.
"""
from __future__ import annotations

from ..models import SteerMessage, SteerState
from .sql_rows import STEER_FIELDS, columns as _columns, now as _now, params, steer_from, values as _values


class SessionSteerMixin:
    """Requires ``self._sql`` and ``self.get()`` from the composing class."""

    def append(self, message: SteerMessage) -> SteerMessage:
        values = _values(STEER_FIELDS)
        result = self._sql.execute(
            f"INSERT INTO session_steers ({_columns(STEER_FIELDS)}) "
            f"SELECT {values} WHERE EXISTS (SELECT 1 FROM companion_sessions "
            "WHERE tenant_id=:tenant_id AND owner_id=:owner_id "
            "AND session_id=:session_id AND archived_at IS NULL) ON CONFLICT "
            "(tenant_id, owner_id, session_id, send_id) DO NOTHING",
            params(message),
        )
        session = self.get(message.tenant_id, message.owner_id, message.session_id)
        if session is None or session.archived_at is not None:
            raise ValueError("session not found")
        if result.row_count == 1:
            return message
        existing = self._by_send_id(
            message.tenant_id, message.owner_id, message.session_id, message.send_id,
        )
        if existing is None:
            raise RuntimeError("steer deduplication failed")
        return existing

    def get_steer(
        self, tenant_id: str, owner_id: str, session_id: str, delivery_id: str,
    ) -> SteerMessage | None:
        row = self._sql.fetch_one(
            "SELECT * FROM session_steers WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND session_id=:session_id "
            "AND delivery_id=:delivery_id",
            {"tenant_id": tenant_id, "owner_id": owner_id,
             "session_id": session_id, "delivery_id": delivery_id},
        )
        return steer_from(row)

    def list_written(
        self, tenant_id: str, owner_id: str, session_id: str,
    ) -> list[SteerMessage]:
        rows = self._sql.fetch_all(
            "SELECT t.* FROM session_steers t JOIN companion_sessions s ON "
            "s.tenant_id=t.tenant_id AND s.owner_id=t.owner_id AND s.session_id=t.session_id "
            "WHERE t.tenant_id=:tenant_id AND t.owner_id=:owner_id "
            "AND t.session_id=:session_id AND t.state='written' AND s.archived_at IS NULL "
            "ORDER BY t.created_at, t.delivery_id",
            {"tenant_id": tenant_id, "owner_id": owner_id, "session_id": session_id},
        )
        return [item for row in rows if (item := steer_from(row)) is not None]

    def transition(
        self, tenant_id: str, owner_id: str, session_id: str, delivery_id: str,
        state: SteerState, expected_revision: int,
    ) -> SteerMessage | None:
        if state is SteerState.WRITTEN:
            return None
        now = _now()
        result = self._sql.execute(
            "UPDATE session_steers SET state=:state, consumed_at=:consumed_at, "
            "requeued_at=:requeued_at, revision=revision+1 "
            "WHERE tenant_id=:tenant_id AND owner_id=:owner_id "
            "AND session_id=:session_id AND delivery_id=:delivery_id "
            "AND revision=:expected_revision AND state='written' "
            "AND EXISTS (SELECT 1 FROM companion_sessions WHERE "
            "tenant_id=:tenant_id AND owner_id=:owner_id "
            "AND session_id=:session_id AND archived_at IS NULL)",
            {"tenant_id": tenant_id, "owner_id": owner_id, "session_id": session_id,
             "delivery_id": delivery_id, "state": state.value,
             "consumed_at": now if state is SteerState.CONSUMED else None,
             "requeued_at": now if state is SteerState.REQUEUED else None,
             "expected_revision": expected_revision},
        )
        value = self.get_steer(tenant_id, owner_id, session_id, delivery_id)
        return value if result.row_count == 1 and isinstance(value, SteerMessage) else None

    def reconcile_written(self) -> list[SteerMessage]:
        from .sql_recovery import reconcile_written
        return reconcile_written(self._sql, self.transition)

    def _by_send_id(
        self, tenant_id: str, owner_id: str, session_id: str, send_id: str,
    ) -> SteerMessage | None:
        row = self._sql.fetch_one(
            "SELECT * FROM session_steers WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND session_id=:session_id AND send_id=:send_id",
            {"tenant_id": tenant_id, "owner_id": owner_id,
             "session_id": session_id, "send_id": send_id},
        )
        return steer_from(row)


__all__ = ["SessionSteerMixin"]

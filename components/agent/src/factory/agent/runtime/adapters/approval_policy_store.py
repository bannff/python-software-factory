"""Durable owner-scoped Agent tool approval policy store."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..approval_policy import ApprovalPolicy, StaleApprovalPolicy


class SqliteApprovalPolicyStore:
    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS agent_approval_policies (
                tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL,
                tool_names TEXT NOT NULL, revision INTEGER NOT NULL,
                PRIMARY KEY (tenant_id, owner_id))""")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def get(self, tenant_id: str, owner_id: str) -> ApprovalPolicy:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT tool_names, revision FROM agent_approval_policies "
                "WHERE tenant_id=? AND owner_id=?", (tenant_id, owner_id),
            ).fetchone()
        return ApprovalPolicy() if row is None else ApprovalPolicy(
            tool_names=tuple(json.loads(row[0])), revision=int(row[1]),
        )

    def update(
        self, tenant_id: str, owner_id: str, expected_revision: int, *,
        tool_names: tuple[str, ...],
    ) -> ApprovalPolicy:
        candidate = ApprovalPolicy(tool_names=tool_names)
        encoded = json.dumps(candidate.tool_names, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT revision FROM agent_approval_policies "
                "WHERE tenant_id=? AND owner_id=?", (tenant_id, owner_id),
            ).fetchone()
            revision = 0 if current is None else int(current[0])
            if revision != expected_revision:
                conn.rollback()
                raise StaleApprovalPolicy("stale approval policy")
            next_revision = revision + 1
            if current is None:
                conn.execute(
                    "INSERT INTO agent_approval_policies VALUES (?, ?, ?, ?)",
                    (tenant_id, owner_id, encoded, next_revision),
                )
            else:
                result = conn.execute(
                    "UPDATE agent_approval_policies SET tool_names=?, revision=? "
                    "WHERE tenant_id=? AND owner_id=? AND revision=?",
                    (encoded, next_revision, tenant_id, owner_id, revision),
                )
                if result.rowcount != 1:
                    conn.rollback()
                    raise StaleApprovalPolicy("stale approval policy")
            conn.commit()
        return ApprovalPolicy(tool_names=candidate.tool_names, revision=next_revision)


__all__ = ["SqliteApprovalPolicyStore"]

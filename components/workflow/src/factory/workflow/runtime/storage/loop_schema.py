"""SQLite schema for Workflow loop policy and child linkage."""
from __future__ import annotations

import sqlite3


def init_loop_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workflow_loops (
            tenant_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            loop_id TEXT NOT NULL,
            state TEXT NOT NULL,
            revision INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            PRIMARY KEY (tenant_id, owner_id, loop_id)
        );
        CREATE INDEX IF NOT EXISTS idx_workflow_loops_active
            ON workflow_loops(state, updated_at, loop_id);
        CREATE TABLE IF NOT EXISTS workflow_loop_cycles (
            tenant_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            loop_id TEXT NOT NULL,
            cycle INTEGER NOT NULL,
            schedule_id TEXT NOT NULL UNIQUE,
            workflow_run_id TEXT UNIQUE,
            state TEXT NOT NULL,
            revision INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            PRIMARY KEY (tenant_id, owner_id, loop_id, cycle),
            FOREIGN KEY (tenant_id, owner_id, loop_id)
                REFERENCES workflow_loops(tenant_id, owner_id, loop_id)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_workflow_loop_cycles_state
            ON workflow_loop_cycles(state, updated_at, loop_id, cycle);
    """)


__all__ = ["init_loop_schema"]

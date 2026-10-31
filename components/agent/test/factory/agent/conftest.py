"""Hermetic session-store isolation for agent-brick tests.

The phase-2 durable session repository defaults to the shared
``./.storage/strands-sessions.db``; tests that build ``StrandsChatAgent``
fakes must never touch (or leak into) that real file. Autouse here:
every test in the brick runs with the strands sessions DB redirected to
a per-test temp path. Opt into the REAL default only in explicit
durability tests that set the env var themselves.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_strands_sessions_db(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "COMPANION_X_STRANDS_SESSIONS_DB_PATH",
        str(tmp_path / "strands-sessions.db"),
    )

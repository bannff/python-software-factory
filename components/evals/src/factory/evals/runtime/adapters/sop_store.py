"""File-backed SOP session store.

Persists sessions to .object_store/sop_sessions.json using atomic writes
(write to temp file, os.replace) to avoid corruption from concurrent access.
"""
from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sop_adapter import SOPState

_STORE_PATH = Path(".object_store/sop_sessions.json")
_TMP_PATH = Path(".object_store/sop_sessions.json.tmp")

_cache: dict | None = None


def _ensure_dir() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_all() -> dict[str, "SOPState"]:
    """Load all sessions from disk. Returns empty dict if file missing."""
    global _cache
    if _cache is not None:
        return _cache
    _cache = _deserialize(_read_raw())
    return _cache


def save_all(sessions: dict[str, "SOPState"]) -> None:
    """Atomically persist all sessions to disk."""
    global _cache
    _cache = sessions
    _ensure_dir()
    raw = {sid: dataclasses.asdict(s) for sid, s in sessions.items()}
    _TMP_PATH.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    os.replace(_TMP_PATH, _STORE_PATH)


def load_session(session_id: str) -> "SOPState | None":
    """Load a single session by ID. Returns None if not found."""
    return load_all().get(session_id)


def save_session(state: "SOPState") -> None:
    """Persist a single session (merges into full store)."""
    sessions = load_all()
    sessions[state.id] = state
    save_all(sessions)


# ── internals ────────────────────────────────────────────────────────────────

def _read_raw() -> dict:
    try:
        return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _deserialize(raw: dict) -> dict[str, "SOPState"]:
    from .sop_adapter import SOPState
    result: dict[str, SOPState] = {}
    for sid, data in raw.items():
        try:
            result[sid] = SOPState(**data)
        except Exception:
            pass
    return result

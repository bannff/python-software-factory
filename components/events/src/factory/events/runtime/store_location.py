"""Which events SQLite file is live, and whether a second one is lying around (#382).

The launcher pins one absolute path, but a hand-started API falls back to
``./events.db``. Readers that hardcode either path then see stale history, so
health names the live file and any other store sitting in the workspace.
"""
from __future__ import annotations

import os
from pathlib import Path

_CANDIDATES = ("events.db", ".storage/events.db")


def live_store_path() -> Path:
    raw = (os.environ.get("EVENTS_HISTORY_SQLITE_PATH")
           or os.environ.get("EVENTS_SQLITE_PATH") or "./events.db")
    return Path(raw).expanduser().resolve()


def stray_stores(live: Path, root: Path | None = None) -> list[str]:
    base = root or Path.cwd()
    found = (Path(base, rel).resolve() for rel in _CANDIDATES)
    return [str(path) for path in found if path != live and path.is_file()]


__all__ = ["live_store_path", "stray_stores"]

"""Archive adapters — file-backed JSONL + in-memory fake.

JSONL adapter: append-only, one line per record, never truncates.
InMemoryArchive: test fake accumulating records in a list.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..archive_ports import ArchiveSinkPort


class JsonlFileArchive:
    """Append-only JSONL file archive — satisfies ArchiveSinkPort.

    One file per agent_id. Records are appended as single JSON lines.
    Never truncates — safe for crash recovery.
    """

    def __init__(self, storage_dir: str | Path) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, agent_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in agent_id)
        return self._dir / f"{safe}.jsonl"

    def append(self, agent_id: str, record: dict[str, Any]) -> None:
        """Append one record as a JSON line (append mode — never truncates)."""
        path = self._path_for(agent_id)
        line = json.dumps(record, default=str) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

    def read_all(self, agent_id: str) -> list[dict[str, Any]]:
        """Read all records for an agent (for testing/inspection)."""
        path = self._path_for(agent_id)
        if not path.exists():
            return []
        records = []
        for line in path.read_text("utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records


class InMemoryArchive:
    """In-memory archive for testing — satisfies ArchiveSinkPort."""

    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, Any]]] = []

    def append(self, agent_id: str, record: dict[str, Any]) -> None:
        self.records.append((agent_id, record))

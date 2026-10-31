"""File-backed persistence adapter — satisfies RunnerPersistencePort.

Stores each agent's state as a JSON file. Uses atomic writes
(tmp file + os.replace) to prevent corruption on crash.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ..agent_runner_models import AgentRunnerState
from ..agent_runner_ports import RunnerPersistencePort


class FilePersistence:
    """File-backed RunnerPersistencePort — one JSON file per agent."""

    def __init__(self, storage_dir: str | Path) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, agent_id: str) -> Path:
        # Safe filename: replace non-alnum with underscore
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in agent_id)
        return self._dir / f"{safe}.json"

    async def save_state(self, state: AgentRunnerState) -> None:
        """Persist state atomically (write to tmp + os.replace)."""
        target = self._path_for(state.agent_id)
        data = json.dumps(state.to_dict(), indent=2)

        # Write to a tmp file in the same directory then atomically rename
        fd, tmp_path = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
        try:
            os.write(fd, data.encode("utf-8"))
            os.fsync(fd)
            os.close(fd)
            os.replace(tmp_path, target)
        except BaseException:
            os.close(fd) if not os.get_inheritable(fd) else None  # pragma: no cover
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    async def load_state(self, agent_id: str) -> AgentRunnerState | None:
        """Load persisted state. Returns None if no file exists."""
        target = self._path_for(agent_id)
        if not target.exists():
            return None
        data = json.loads(target.read_text("utf-8"))
        return AgentRunnerState.from_dict(data)

    async def list_agents(self) -> list[str]:
        """List all agent_ids with persisted state files."""
        agents = []
        for path in self._dir.glob("*.json"):
            try:
                data = json.loads(path.read_text("utf-8"))
                agents.append(data["agent_id"])
            except (json.JSONDecodeError, KeyError):
                continue  # Skip corrupted files
        return agents

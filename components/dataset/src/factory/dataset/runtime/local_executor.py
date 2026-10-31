"""Detached subprocess dispatcher for the local durable dataset worker."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import factory.dataset


class LocalDatasetExecutor:
    """Detached subprocess dispatcher for the local durable worker."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def submit(self, job_id: str) -> None:
        src_dir = Path(factory.dataset.__file__).parent.parent.parent
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            [str(src_dir)] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
        )
        log_path = self.root / "jobs" / f"{job_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", buffering=1) as log_file:
            subprocess.Popen(
                [sys.executable, "-m", "factory.dataset", str(self.root), job_id],
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,
                env=env,
            )

"""Package entry point that delegates to the detached CLI worker."""

from __future__ import annotations

from pathlib import Path
import sys

from .cli import main

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m factory.dataset <storage_root> <job_id>")
    main(Path(sys.argv[1]), sys.argv[2])

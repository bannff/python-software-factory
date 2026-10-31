"""Side-effecting writer — the only IO in the control-plane runtime.

Decide (resolve + serialize) elsewhere; this only acts.
"""

from __future__ import annotations

from pathlib import Path


def write_config(path: Path, content: str) -> None:
    """Write content to path, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

"""Immutable source snapshots for attempt-bound CAN execution."""
from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
from typing import Any

from .atomic_io import atomic_write_immutable, read_bytes_no_follow
from .can_terminal_canonical import CanonicalCanRequest
from .can_terminal_paths import checked_output_path


def snapshot_sources(
    canonical: CanonicalCanRequest, root: Path,
) -> CanonicalCanRequest:
    """Copy verified source bytes once and return paths used by all effects."""
    output = checked_output_path(
        root, root / "can_terminal" / "sources" / canonical.request_sha256,
    )
    mf4 = tuple(
        _snapshot(path, item, output, f"mf4-{index}")
        for index, (path, item) in enumerate(
            zip(canonical.mf4_paths, canonical.payload["mf4"], strict=True)
        )
    )
    dbc = _snapshot(canonical.dbc_path, canonical.payload["dbc"], output, "dbc")
    contexts = tuple(
        _snapshot(path, item, output, f"context-{index}")
        for index, (path, item) in enumerate(zip(
            canonical.context_paths,
            canonical.payload["context_sources"], strict=True,
        ))
    )
    return replace(
        canonical, mf4_paths=mf4, dbc_path=dbc, context_paths=contexts,
    )


def _snapshot(
    source: Path, inventory: dict[str, Any], output: Path, label: str,
) -> Path:
    content = read_bytes_no_follow(source)
    digest = hashlib.sha256(content).hexdigest()
    if digest != inventory.get("sha256"):
        raise ValueError(f"CAN source changed after request binding: {label}")
    suffix = source.suffix.lower() or ".bin"
    target = checked_output_path(output.parents[2], output / f"{label}-{digest}{suffix}")
    atomic_write_immutable(target, content)
    return target


__all__ = ["snapshot_sources"]

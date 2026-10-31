"""Shared helpers for the local durable dataset adapter."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any


def _now() -> datetime:
    return datetime.now(UTC)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _config_digest(config: dict | None) -> str:
    config_content = json.dumps(config or {}, sort_keys=True, separators=(",", ":")).encode()
    return _sha256(config_content)


def _verify_snapshot_ref(snapshot, *, label: str) -> None:
    from .recipe import path_from_uri
    from .atomic_io import read_bytes_no_follow

    snapshot_path = path_from_uri(snapshot.uri)
    try:
        content = read_bytes_no_follow(snapshot_path)
    except FileNotFoundError:
        raise ValueError(f"{label} snapshot is missing") from None
    if _sha256(content) != snapshot.digest:
        raise ValueError(f"{label} snapshot digest does not match its reference")


def _write_immutable(path: Path, content: bytes) -> None:
    from .atomic_io import atomic_write_immutable
    atomic_write_immutable(path, content)


def load_records_from_uri(uri: str) -> list[dict[str, Any]]:
    """Load CAN frame records from a file:// URI (JSONL).

    Shared by can_profile, can_synthesize, and can_window adapters
    when run standalone (materializer passes empty records for
    can_frame schema recipes).
    """
    from urllib.parse import unquote, urlparse
    parsed = urlparse(uri)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"Only file:// URIs are supported: {uri}")
    raw_path = unquote(parsed.path) if parsed.scheme == "file" else uri
    if ".." in Path(raw_path).parts:
        raise ValueError(f"Path traversal not allowed: {uri}")
    path = Path(raw_path).resolve()
    from .atomic_io import read_bytes_no_follow
    records: list[dict[str, Any]] = []
    for line in read_bytes_no_follow(path).splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records

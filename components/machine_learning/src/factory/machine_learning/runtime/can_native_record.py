"""Immutable effect-specific replay records for native CAN training."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any

from .can_lifecycle_canonical import canonical_json
from .mlx_publication import sealed_local_model_artifact_digest

_RECORD_VERSION = "ml-can-native-training-record@v1"


def publish_native_record(
    root: Path, effect_id: str, binding: dict[str, Any], row: dict[str, Any],
) -> dict[str, Any]:
    """Seal model bytes and create-or-match one exact replay record."""
    model_path = Path(row["model_path"])
    model_digest = sealed_local_model_artifact_digest(
        model_path, seal_unsealed=True,
    )
    body = {
        "record_version": _RECORD_VERSION, "effect_id": effect_id,
        "binding": binding, "model_digest": model_digest, "row": row,
    }
    content = canonical_json(body)
    path = _record_path(root, effect_id)
    _write_immutable(path, content)
    stored = _read(path)
    if stored != body:
        raise ValueError("native training record differs from exact effect")
    return {**row, "artifact_seal": {
        "uri": path.as_uri(), "sha256": hashlib.sha256(content).hexdigest(),
        "model_digest": model_digest,
    }}


def replay_native_record(
    root: Path, effect_id: str, binding: dict[str, Any],
) -> dict[str, Any] | None:
    """Authenticate and replay a completed native training effect."""
    path = _record_path(root, effect_id)
    if not path.exists():
        return None
    value = _read(path)
    if (
        value.get("record_version") != _RECORD_VERSION
        or value.get("effect_id") != effect_id or value.get("binding") != binding
    ):
        raise ValueError("native training record does not match exact request")
    row = value.get("row")
    if not isinstance(row, dict):
        raise ValueError("native training record row is malformed")
    model_path = Path(str(row.get("model_path", "")))
    observed = sealed_local_model_artifact_digest(model_path)
    if observed != value.get("model_digest"):
        raise ValueError("native model differs from sealed training record")
    content = canonical_json(value)
    return {**row, "artifact_seal": {
        "uri": path.as_uri(), "sha256": hashlib.sha256(content).hexdigest(),
        "model_digest": observed,
    }}


def _record_path(root: Path, effect_id: str) -> Path:
    directory = root / "native_training"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{effect_id}.json"


def _read(path: Path) -> dict[str, Any]:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
        or info.st_mode & 0o222 or path.is_symlink()
    ):
        raise ValueError("native training record is not immutable")
    content = path.read_bytes()
    value = json.loads(content)
    if not isinstance(value, dict) or canonical_json(value) != content:
        raise ValueError("native training record is not canonical")
    return value


def _write_immutable(path: Path, content: bytes) -> None:
    try:
        descriptor = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444,
        )
    except FileExistsError:
        if path.read_bytes() != content:
            raise ValueError("immutable native training record already differs")
        return
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content); stream.flush(); os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


__all__ = ["publish_native_record", "replay_native_record"]

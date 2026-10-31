"""Request-bound immutable seals for lifecycle-owned LightGBM trees."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any

from .can_lifecycle_canonical import canonical_json
from .passport_tree_manifest import bounded_tree_manifest
from .passport_tree_seal import require_read_only_tree, seal_read_only_tree

_SEAL_NAME = "lightgbm-artifact-seal.json"
_BINDING_KEYS = {
    "schema_version", "effect_id", "artifact_refs", "training_config",
    "can_id", "rank", "experiment_name", "model_tree_sha256", "seal_sha256",
}


def seal_lightgbm_artifact(
    model_path: Path, root: Path, *, effect_id: str,
    refs: dict[str, dict[str, Any]], config: dict[str, Any],
    can_id: str, rank: int, experiment_name: str,
    effect_dir: Path | None = None,
) -> dict[str, str]:
    """Seal one validated native tree and publish its exact request binding."""
    manifest = bounded_tree_manifest(model_path, root, "LightGBM artifact")
    seal_read_only_tree(model_path)
    require_read_only_tree(model_path)
    if bounded_tree_manifest(model_path, root, "LightGBM artifact") != manifest:
        raise ValueError("LightGBM artifact changed while sealing")
    tree_digest = hashlib.sha256(canonical_json(manifest)).hexdigest()
    values = _binding(
        effect_id, refs, config, can_id, rank, experiment_name, tree_digest,
    )
    content = canonical_json(values)
    path = _seal_path(root, effect_id, effect_dir)
    _write_immutable(path, content)
    return _reference(path, values)


def verify_lightgbm_artifact(
    model_path: Path, root: Path, *, effect_id: str,
    refs: dict[str, dict[str, Any]], config: dict[str, Any],
    can_id: str, rank: int, experiment_name: str,
    effect_dir: Path | None = None,
) -> dict[str, str]:
    """Require an exact seal, complete tree digest, and read-only native tree."""
    path = _seal_path(root, effect_id, effect_dir)
    value = _read_seal(path)
    require_read_only_tree(model_path)
    manifest = bounded_tree_manifest(model_path, root, "LightGBM artifact")
    tree_digest = hashlib.sha256(canonical_json(manifest)).hexdigest()
    expected = _binding(
        effect_id, refs, config, can_id, rank, experiment_name, tree_digest,
    )
    if value != expected:
        raise ValueError("LightGBM artifact seal does not match the exact request")
    return _reference(path, value)


def _binding(effect_id, refs, config, can_id, rank, experiment_name, tree_digest):
    body = {
        "schema_version": "1.0", "effect_id": effect_id,
        "artifact_refs": refs, "training_config": config,
        "can_id": can_id, "rank": rank, "experiment_name": experiment_name,
        "model_tree_sha256": tree_digest,
    }
    return {**body, "seal_sha256": hashlib.sha256(canonical_json(body)).hexdigest()}


def _read_seal(path: Path) -> dict[str, Any]:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
        or info.st_mode & 0o222 or path.is_symlink()
    ):
        raise ValueError("LightGBM artifact seal is not immutable")
    content = path.read_bytes()
    value = json.loads(content)
    if canonical_json(value) != content or set(value) != _BINDING_KEYS:
        raise ValueError("LightGBM artifact seal is not canonical and exact")
    observed = value["seal_sha256"]
    body = {key: item for key, item in value.items() if key != "seal_sha256"}
    if observed != hashlib.sha256(canonical_json(body)).hexdigest():
        raise ValueError("LightGBM artifact seal digest mismatch")
    return value


def _seal_path(root: Path, effect_id: str, effect_dir: Path | None) -> Path:
    return (effect_dir if effect_dir is not None else root / effect_id) / _SEAL_NAME


def _reference(path: Path, value: dict[str, Any]) -> dict[str, str]:
    return {
        "uri": path.as_uri(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "model_tree_sha256": value["model_tree_sha256"],
    }


def _write_immutable(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError:
        if path.read_bytes() != content:
            raise ValueError("immutable LightGBM artifact seal already differs")
        return
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content); stream.flush(); os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


__all__ = ["seal_lightgbm_artifact", "verify_lightgbm_artifact"]

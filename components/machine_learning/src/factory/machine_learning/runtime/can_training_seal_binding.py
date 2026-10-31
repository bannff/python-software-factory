"""Trusted training-seal checks for lifecycle passport boundaries."""
from __future__ import annotations

import hashlib
from pathlib import Path
import stat
from typing import Any
from urllib.parse import unquote, urlparse

from .mlx_publication import sealed_local_model_artifact_digest
from .passport_trees import mlflow_lightgbm_artifact_ref


def require_training_model_seal(row: dict[str, Any], storage_root: Path) -> None:
    """Authenticate the sealed record and current family model bytes."""
    seal = row.get("artifact_seal")
    if not isinstance(seal, dict):
        raise ValueError("training row lacks its trusted artifact seal")
    record = _local_path(str(seal.get("uri", "")))
    _require_contained(record, storage_root)
    info = record.lstat()
    if (
        not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
        or info.st_mode & 0o222 or record.is_symlink()
        or hashlib.sha256(record.read_bytes()).hexdigest() != seal.get("sha256")
    ):
        raise ValueError("trusted training record differs from its seal")
    model = Path(str(row["model_path"]))
    _require_contained(model, storage_root)
    if "model_tree_sha256" in seal:
        observed = mlflow_lightgbm_artifact_ref(
            "model", model, storage_root,
        ).digest
        expected = seal["model_tree_sha256"]
    else:
        observed = sealed_local_model_artifact_digest(model)
        expected = seal.get("model_digest")
    if observed != expected:
        raise ValueError("model differs from trusted training seal")


def _require_contained(path: Path, root: Path) -> None:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError("training seal path escapes passport authority") from exc


def _local_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError("training record seal requires a local file URI")
    return Path(unquote(parsed.path))


__all__ = ["require_training_model_seal"]

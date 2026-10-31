"""Private immutable-object staging and pointer publication for MLX."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import uuid

import numpy as np

from ..durable_files import fsync_directory, fsync_tree
from ..mlx_publication import (
    publication_lock, publish_mlx_reference, verified_mlx_tree,
)
from ..passport_tree_seal import (
    remove_staging_tree, require_read_only_tree, seal_read_only_tree,
)
from ..passport_trees import mlx_safetensors_artifact_ref, mlx_tree_manifest
from ..ports import TimeSeriesModelType
from .mlx_native import (
    passport_config, validate_pinned_tree, validate_unsealed_tree, write_native_tree,
)


def persist_native_model(
    durable_root: Path, model: Any, model_type: TimeSeriesModelType,
    input_size: int, window_size: int, num_classes: int,
    scaler_mean: np.ndarray, scaler_scale: np.ndarray,
) -> Path:
    """Build and seal a unique hidden object, then exclusively publish its ref."""
    object_path = durable_root / f".{uuid.uuid4()}.mlx-object"
    object_path.mkdir(mode=0o700, parents=False, exist_ok=False)
    sealed = False
    try:
        write_native_tree(
            object_path, model, model_type, input_size, window_size, num_classes,
            scaler_mean, scaler_scale,
        )
        validate_unsealed_tree(object_path)
        before = mlx_tree_manifest(object_path, durable_root)
        artifact = mlx_safetensors_artifact_ref("model", object_path, durable_root)
        fsync_tree(object_path)
        reference = durable_root / artifact.digest
        with publication_lock(reference):
            if reference.exists() or reference.is_symlink():
                _verify_reference(reference, artifact.digest)
                fsync_directory(durable_root)
                remove_staging_tree(object_path)
                return reference
            orphan = _sealed_orphan(durable_root, object_path, artifact.digest)
            if orphan is not None:
                remove_staging_tree(object_path)
                publish_mlx_reference(reference, orphan, artifact.digest)
                _verify_reference(reference, artifact.digest)
                return reference
            seal_read_only_tree(object_path)
            sealed = True
            fsync_tree(object_path)
            require_read_only_tree(object_path)
            if mlx_tree_manifest(object_path, durable_root) != before:
                raise ValueError("MLX artifact bytes changed while sealing")
            fsync_directory(durable_root)
            publish_mlx_reference(reference, object_path, artifact.digest)
            _verify_reference(reference, artifact.digest)
            return reference
    except Exception:
        if not sealed:
            remove_staging_tree(object_path)
        raise


def _sealed_orphan(root: Path, current: Path, digest: str) -> Path | None:
    """Find an exact fully sealed crash orphan without modifying debris."""
    for candidate in sorted(root.glob(".*.mlx-object")):
        if candidate == current:
            continue
        try:
            require_read_only_tree(candidate)
            validate_unsealed_tree(candidate)
            observed = mlx_safetensors_artifact_ref("model", candidate, root).digest
            require_read_only_tree(candidate)
        except (OSError, RuntimeError, ValueError):
            continue
        if observed == digest:
            return candidate
    return None


def _verify_reference(reference: Path, digest: str) -> None:
    with verified_mlx_tree(reference, digest) as tree:
        validate_pinned_tree(tree)
    passport_config(reference)


__all__ = ["persist_native_model"]

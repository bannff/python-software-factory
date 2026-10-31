"""Pointer-aware and legacy local model digest dispatch."""
from __future__ import annotations

from pathlib import Path

from .passport_tree_seal import require_read_only_tree


def is_mlx_reference_path(value: Path) -> bool:
    """Recognize digest-shaped MLX authority files, including malformed ones."""
    return len(value.name) == 64 and all(c.lower() in "0123456789abcdef" for c in value.name)


def sealed_local_model_artifact_digest(
    path: str | Path, *, seal_unsealed: bool = False,
) -> str:
    """Digest through pointer authority; seal only ordinary model trees."""
    from .passport_trees import local_model_artifact_digest
    value = Path(path)
    if is_mlx_reference_path(value):
        return local_model_artifact_digest(value)
    tree = value if value.is_dir() else value.parent
    if seal_unsealed:
        from .passport_tree_seal import seal_read_only_tree
        seal_read_only_tree(tree)
    require_read_only_tree(tree)
    return local_model_artifact_digest(value)


__all__ = ["is_mlx_reference_path", "sealed_local_model_artifact_digest"]

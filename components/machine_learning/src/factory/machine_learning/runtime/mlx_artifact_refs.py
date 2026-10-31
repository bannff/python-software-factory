"""MLX pointer-aware artifact references and exact verification."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .mlx_publication import verified_mlx_tree
from .passport_refs import PassportArtifactRef
from .passport_validation import canonical_json

_MEDIA_TYPE = "application/vnd.apple.mlx.safetensors"
_FORMAT = "mlx-safetensors"


def mlx_artifact_ref(
    role: str, path: str | Path, storage_root: str | Path,
) -> PassportArtifactRef:
    """Create an MLX ref from a private object or canonical pointer."""
    from .passport_trees import mlx_tree_manifest
    value = Path(path)
    if value.is_file():
        with verified_mlx_tree(value) as tree:
            manifest = tree.manifest
        uri = value.absolute().as_uri()
    else:
        manifest = mlx_tree_manifest(value, storage_root)
        uri = value.resolve().as_uri()
    digest = hashlib.sha256(canonical_json(manifest)).hexdigest()
    return PassportArtifactRef(
        role=role, uri=uri, digest=digest, media_type=_MEDIA_TYPE,
        format=_FORMAT, size_bytes=manifest["total_size_bytes"],
    )


def verify_mlx_artifact_ref(
    ref: PassportArtifactRef, storage_root: str | Path,
) -> None:
    """Bracket and verify a canonical MLX pointer against exact object bytes."""
    path = _file_path(ref.uri)
    with verified_mlx_tree(path, ref.digest) as tree:
        manifest = tree.manifest
    mismatch = (
        path.absolute().as_uri() != ref.uri
        or ref.media_type != _MEDIA_TYPE
        or hashlib.sha256(canonical_json(manifest)).hexdigest() != ref.digest
        or manifest["total_size_bytes"] != ref.size_bytes
    )
    if mismatch:
        raise ValueError(f"{ref.role} model tree does not match exact bytes")


def _file_path(uri: str) -> Path:
    from urllib.parse import unquote, urlparse
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError("model tree artifacts require file URIs")
    return Path(unquote(parsed.path))


__all__ = ["mlx_artifact_ref", "verify_mlx_artifact_ref"]

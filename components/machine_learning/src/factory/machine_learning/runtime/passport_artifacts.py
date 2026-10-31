"""Exact local-file references for immutable model-passport artifacts."""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import unquote, urlparse

from .passport_paths import require_contained_file
from .passport_refs import PassportArtifactRef

_FORMATS = {
    ".json": ("application/json", "json"),
    ".jsonl": ("application/x-ndjson", "jsonl"),
    ".npy": ("application/octet-stream", "npy"),
    ".joblib": ("application/octet-stream", "joblib"),
    ".pt": ("application/octet-stream", "pytorch"),
}


def file_artifact_ref(
    role: str, uri_or_path: str, expected_digest: str | None = None,
) -> PassportArtifactRef:
    path = _file_path(uri_or_path)
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise ValueError(f"{role} artifact is missing, not a file, or a symlink")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_digest is not None and digest != expected_digest:
        raise ValueError(f"{role} artifact digest does not match")
    media_type, artifact_format = _FORMATS.get(
        path.suffix.lower(), ("application/octet-stream", "binary"),
    )
    return PassportArtifactRef(
        role=role, uri=path.resolve().as_uri(), digest=digest,
        media_type=media_type, format=artifact_format, size_bytes=len(raw),
    )


def verify_file_artifact_ref(ref: PassportArtifactRef, storage_root: str | Path) -> None:
    """Re-derive and compare an exact local reference beneath ``storage_root``."""
    path = require_contained_file(_file_path(ref.uri), Path(storage_root))
    raw = path.read_bytes()
    media_type, artifact_format = _FORMATS.get(
        path.suffix.lower(), ("application/octet-stream", "binary"),
    )
    if (
        path.resolve().as_uri() != ref.uri
        or hashlib.sha256(raw).hexdigest() != ref.digest
        or len(raw) != ref.size_bytes
        or media_type != ref.media_type
        or artifact_format != ref.format
    ):
        raise ValueError(f"{ref.role} artifact reference does not match exact bytes")


def verify_artifact_ref(ref: PassportArtifactRef, storage_root: str | Path) -> None:
    """Verify a regular file or the complete supported MLflow flavor tree."""
    if ref.format in {
        "mlflow-lightgbm", "transformers-patchtst", "mlx-safetensors",
        "chronos2-native-probe", "chronos2-backbone",
    }:
        from .passport_trees import verify_model_tree_artifact_ref
        verify_model_tree_artifact_ref(ref, storage_root)
        return
    verify_file_artifact_ref(ref, storage_root)


def _file_path(value: str) -> Path:
    parsed = urlparse(value)
    if parsed.scheme not in {"", "file"}:
        raise ValueError("local model-passport artifacts must use file URIs")
    return Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(value)


__all__ = ["file_artifact_ref", "verify_artifact_ref", "verify_file_artifact_ref"]

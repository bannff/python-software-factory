"""Deterministic bounded complete-tree references for approved native formats."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from .passport_paths import require_contained_directory
from .passport_refs import PassportArtifactRef
from .passport_tree_manifest import bounded_tree_manifest
from .passport_tree_seal import require_read_only_tree
from .passport_validation import canonical_json

_FORMATS: dict[str, tuple[str, str, frozenset[str]]] = {
    "mlflow-lightgbm": (
        "application/vnd.mlflow.model", "MLflow flavor", frozenset(),
    ),
    "transformers-patchtst": (
        "application/vnd.huggingface.transformers.model", "PatchTST model",
        frozenset(),
    ),
    "mlx-safetensors": (
        "application/vnd.apple.mlx.safetensors", "MLX safetensors",
        frozenset({"model.safetensors", "factory_model.json"}),
    ),
    "chronos2-native-probe": (
        "application/vnd.amazon.chronos2.native-probe", "Chronos-2 native probe",
        frozenset({
            "backbone/config.json", "backbone/factory_acquisition.json",
            "backbone/model.safetensors", "probe/probe.pt",
        }),
    ),
    "chronos2-backbone": (
        "application/vnd.amazon.chronos2.backbone", "Chronos-2 backbone",
        frozenset({"config.json", "factory_acquisition.json", "model.safetensors"}),
    ),
}
_SEALED = frozenset({"mlx-safetensors", "chronos2-native-probe", "chronos2-backbone"})


def flavor_tree_manifest(path: str | Path, storage_root: str | Path) -> dict[str, Any]:
    return _manifest(path, storage_root, "mlflow-lightgbm")


def patchtst_tree_manifest(path: str | Path, storage_root: str | Path) -> dict[str, Any]:
    return _manifest(path, storage_root, "transformers-patchtst")


def mlx_tree_manifest(path: str | Path, storage_root: str | Path) -> dict[str, Any]:
    return _manifest(path, storage_root, "mlx-safetensors")


def chronos_tree_manifest(path: str | Path, storage_root: str | Path) -> dict[str, Any]:
    return _manifest(path, storage_root, "chronos2-native-probe")


def chronos_backbone_manifest(path: str | Path, storage_root: str | Path) -> dict[str, Any]:
    return _manifest(path, storage_root, "chronos2-backbone")


def _manifest(
    path: str | Path, storage_root: str | Path, artifact_format: str,
) -> dict[str, Any]:
    _, identity, required = _FORMATS[artifact_format]
    return bounded_tree_manifest(path, storage_root, identity, required)


def mlflow_lightgbm_artifact_ref(
    role: str, path: str | Path, storage_root: str | Path,
) -> PassportArtifactRef:
    return _tree_ref(role, path, storage_root, "mlflow-lightgbm", flavor_tree_manifest)


def transformers_patchtst_artifact_ref(
    role: str, path: str | Path, storage_root: str | Path,
) -> PassportArtifactRef:
    return _tree_ref(
        role, path, storage_root, "transformers-patchtst", patchtst_tree_manifest,
    )


def mlx_safetensors_artifact_ref(
    role: str, path: str | Path, storage_root: str | Path,
) -> PassportArtifactRef:
    from .mlx_artifact_refs import mlx_artifact_ref
    return mlx_artifact_ref(role, path, storage_root)


def chronos_native_artifact_ref(
    role: str, path: str | Path, storage_root: str | Path,
) -> PassportArtifactRef:
    return _tree_ref(
        role, path, storage_root, "chronos2-native-probe", chronos_tree_manifest,
    )


def chronos_backbone_artifact_ref(
    role: str, path: str | Path, storage_root: str | Path,
) -> PassportArtifactRef:
    from .adapters.chronos_identity import MODEL_ID, MODEL_REVISION
    return _tree_ref(
        role, path, storage_root, "chronos2-backbone", chronos_backbone_manifest,
        identity=MODEL_ID, version=MODEL_REVISION,
    )


def _tree_ref(
    role: str, path: str | Path, storage_root: str | Path,
    artifact_format: str, manifest_fn: Callable[..., dict[str, Any]],
    *, identity: str | None = None, version: str | None = None,
) -> PassportArtifactRef:
    manifest = manifest_fn(path, storage_root)
    resolved = require_contained_directory(Path(path), Path(storage_root))
    return PassportArtifactRef(
        role=role, uri=resolved.resolve().as_uri(),
        digest=hashlib.sha256(canonical_json(manifest)).hexdigest(),
        media_type=_FORMATS[artifact_format][0], format=artifact_format,
        size_bytes=manifest["total_size_bytes"], identity=identity, version=version,
    )


def local_model_artifact_digest(path: str | Path) -> str:
    value = Path(path)
    from .mlx_publication import is_mlx_reference_path
    if is_mlx_reference_path(value):
        from .mlx_publication import verified_mlx_tree
        with verified_mlx_tree(value) as tree:
            return tree.manifest_digest
    if not value.is_dir():
        return hashlib.sha256(value.read_bytes()).hexdigest()
    if (value / "factory_model.json").is_file():
        return mlx_safetensors_artifact_ref("model", value, value.parent).digest
    if (value / "probe" / "probe.pt").is_file():
        return chronos_native_artifact_ref("model", value, value.parent).digest
    if (value / "factory_preprocessing.json").is_file():
        return transformers_patchtst_artifact_ref("model", value, value.parent).digest
    return mlflow_lightgbm_artifact_ref("model", value, value.parent).digest


def verify_model_tree_artifact_ref(
    ref: PassportArtifactRef, storage_root: str | Path,
) -> None:
    functions = {
        "mlflow-lightgbm": flavor_tree_manifest,
        "transformers-patchtst": patchtst_tree_manifest,
        "mlx-safetensors": mlx_tree_manifest,
        "chronos2-native-probe": chronos_tree_manifest,
        "chronos2-backbone": chronos_backbone_manifest,
    }
    if ref.format not in functions:
        raise ValueError("unsupported model tree format")
    path = _file_path(ref.uri)
    if ref.format == "mlx-safetensors":
        from .mlx_artifact_refs import verify_mlx_artifact_ref
        verify_mlx_artifact_ref(ref, storage_root)
        return
    if ref.format in _SEALED:
        require_read_only_tree(path)
    manifest = functions[ref.format](path, storage_root)
    if (
        path.resolve().as_uri() != ref.uri
        or ref.media_type != _FORMATS[ref.format][0]
        or hashlib.sha256(canonical_json(manifest)).hexdigest() != ref.digest
        or manifest["total_size_bytes"] != ref.size_bytes
    ):
        raise ValueError(f"{ref.role} model tree does not match exact bytes")
    if ref.format in _SEALED:
        require_read_only_tree(path)


def verify_mlflow_lightgbm_artifact_ref(
    ref: PassportArtifactRef, storage_root: str | Path,
) -> None:
    if ref.format != "mlflow-lightgbm":
        raise ValueError("artifact is not an MLflow LightGBM tree")
    verify_model_tree_artifact_ref(ref, storage_root)


def _file_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError("model tree artifacts require file URIs")
    return Path(unquote(parsed.path))


__all__ = [
    "chronos_backbone_artifact_ref", "chronos_backbone_manifest",
    "chronos_native_artifact_ref", "chronos_tree_manifest", "flavor_tree_manifest",
    "local_model_artifact_digest", "mlflow_lightgbm_artifact_ref",
    "mlx_safetensors_artifact_ref", "mlx_tree_manifest", "patchtst_tree_manifest",
    "transformers_patchtst_artifact_ref", "verify_mlflow_lightgbm_artifact_ref",
    "verify_model_tree_artifact_ref",
]

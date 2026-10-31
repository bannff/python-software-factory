"""Closed CAN model-family bindings for ModelPassport issuance."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from .passport_artifacts import file_artifact_ref
from .passport_refs import ArchitectureBinding, InferenceBinding, PassportArtifactRef
from .passport_trees import (
    chronos_native_artifact_ref, mlflow_lightgbm_artifact_ref,
    mlx_safetensors_artifact_ref, transformers_patchtst_artifact_ref,
)
from .passport_validation import semantic_digest


def model_bindings(
    model_type: str, job: Any, storage_root: str,
) -> tuple[ArchitectureBinding, InferenceBinding, PassportArtifactRef, bool]:
    """Return literal native bindings; the boolean marks candidate eligibility."""
    training = _job_config(job)
    if model_type == "lightgbm":
        return _binding(
            "lightgbm", "lightgbm", "mlflow.lightgbm", "mlflow", training,
            mlflow_lightgbm_artifact_ref("model", str(job.model_path), storage_root),
        )
    if model_type in {"lstm", "tcn"} and getattr(job, "backend", None) == "mlx":
        return _mlx_binding(model_type, job, storage_root, training)
    if model_type in {"lstm", "tcn"}:
        from .adapters.torch_native import passport_config
        return _binding(
            model_type, "torch", "torch.state_dict", "torch",
            {"training": training, **passport_config(str(job.model_path))},
            file_artifact_ref("model", str(job.model_path)),
        )
    if model_type == "lnn":
        from .adapters.lnn_native import passport_config
        return _binding(
            "lnn", "ncps", "ncps.torch.LTC.state_dict", "ncps",
            {"training": training, **passport_config(str(job.model_path))},
            file_artifact_ref("model", str(job.model_path)),
        )
    if model_type == "patchtst":
        from .adapters.patchtst_native import passport_config
        return _binding(
            "patchtst", "transformers", "transformers.patchtst", "transformers",
            {"training": training, **passport_config(str(job.model_path))},
            transformers_patchtst_artifact_ref(
                "model", str(job.model_path), storage_root,
            ),
        )
    if model_type == "chronos":
        from .adapters.chronos_native import passport_config
        return _binding(
            "chronos", "chronos-forecasting", "chronos.Chronos2Pipeline",
            "chronos-forecasting",
            {"training": training, **passport_config(str(job.model_path))},
            chronos_native_artifact_ref("model", str(job.model_path), storage_root),
        )
    return (
        ArchitectureBinding(
            architecture=model_type, framework="torch",
            framework_version=_version("torch"), config=training,
        ),
        InferenceBinding(adapter="unavailable", loader=model_type, version="0"),
        file_artifact_ref("model", str(job.model_path)), False,
    )


def _mlx_binding(
    model_type: str, job: Any, storage_root: str, training: dict[str, Any],
) -> tuple[ArchitectureBinding, InferenceBinding, PassportArtifactRef, bool]:
    from .adapters.mlx_identity import MLX_LIFECYCLE
    from .adapters.mlx_native import passport_config
    if getattr(job, "lifecycle_identity", None) != MLX_LIFECYCLE:
        raise ValueError("MLX training job lifecycle identity is not exact")
    config = {"training": training, **passport_config(str(job.model_path))}
    return (
        ArchitectureBinding(
            architecture=model_type, framework=MLX_LIFECYCLE.framework,
            framework_version=MLX_LIFECYCLE.framework_version, config=config,
        ),
        InferenceBinding(
            adapter="can_inference", loader=MLX_LIFECYCLE.loader,
            version=MLX_LIFECYCLE.framework_version,
        ),
        mlx_safetensors_artifact_ref(
            "model", str(job.model_path), storage_root,
        ), True,
    )


def _binding(
    architecture: str, framework: str, loader: str, package: str,
    config: dict[str, Any], artifact: PassportArtifactRef,
) -> tuple[ArchitectureBinding, InferenceBinding, PassportArtifactRef, bool]:
    return (
        ArchitectureBinding(
            architecture=architecture, framework=framework,
            framework_version=_version(framework), config=config,
        ),
        InferenceBinding(
            adapter="can_inference", loader=loader, version=_version(package),
        ), artifact, True,
    )


def sealed_config(config: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in config.items() if key != "training"}


def _job_config(job: Any) -> dict[str, Any]:
    config = getattr(job, "config", {})
    if is_dataclass(config):
        return asdict(config)
    if isinstance(config, dict):
        return dict(config)
    return {"identity": semantic_digest(str(config))}


def _version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unknown"


__all__ = ["model_bindings", "sealed_config"]

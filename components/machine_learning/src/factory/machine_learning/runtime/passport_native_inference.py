"""Exact-passport cold inference for approved native neural families."""
from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

import numpy as np

from .can_passport_models import sealed_config
from .live_timing import LiveTimingArtifactRef, load_live_timing
from .model_passport import ModelPassport
from .passport_native_contract import (
    LNN_LOADER, MLX_LOADER, require_promoted, validate_contract,
)
from .passport_service import ModelPassportService
from .passport_snapshot import verified_snapshot
from .passport_store_models import ModelPassportRef


def load_neural_passport_scores(
    service: ModelPassportService, ref: ModelPassportRef, X: np.ndarray,
    live_timing: LiveTimingArtifactRef | None = None,
) -> np.ndarray:
    passport = service.get(ref)
    root = service.storage_root
    if not root:
        raise ValueError("passport service has no configured durable root")
    require_promoted(passport)
    predecessor = passport.predecessor
    if (
        predecessor is None or predecessor.model_id != passport.model_id
        or predecessor.model_version != passport.model_version
        or predecessor.passport_revision != 1
    ):
        raise ValueError("neural passport has no exact revision-one predecessor")
    service.get(ModelPassportRef.model_validate(predecessor.model_dump()))
    config = _validated_config(passport, X)
    timespans = _load_production_timing(passport, config, X, live_timing)
    with verified_snapshot(passport, root, ("model",)) as snapshot:
        return _load_scores(passport, snapshot["model"], config, X, timespans)


def _load_neural_snapshot_scores(
    passport: ModelPassport, model_path: str | Path, X: np.ndarray,
    timespans_path: str | Path | None = None,
) -> np.ndarray:
    if not (
        passport.passport_revision == 1
        and passport.promotion_status == "candidate"
        and passport.conformance_status == "not_run"
        and not passport.conformance_evidence
    ):
        raise ValueError("neural snapshot scoring requires an exact candidate")
    config = _validated_config(passport, X)
    timespans = _load_conformance_timing(passport, config, timespans_path)
    return _load_scores(passport, Path(model_path), config, X, timespans)


def _load_production_timing(
    passport: ModelPassport, config: dict, X: np.ndarray,
    ref: LiveTimingArtifactRef | None,
) -> np.ndarray | None:
    if passport.inference.loader != LNN_LOADER:
        if ref is not None:
            raise ValueError("live timing is not accepted for this neural loader")
        return None
    if ref is None:
        raise ValueError("LNN production inference requires live timing")
    return load_live_timing(ref, (len(X), config["window_size"]))


def _load_conformance_timing(
    passport: ModelPassport, config: dict, path: str | Path | None,
) -> np.ndarray | None:
    if passport.inference.loader != LNN_LOADER:
        if path is not None:
            raise ValueError("timing is not accepted for this neural loader")
        return None
    timing = passport.preparation.timespans
    if timing is None or path is None:
        raise ValueError("LNN candidate conformance requires prepared timing")
    from .adapters.lnn_native import timing_artifact
    values, scale, digest = timing_artifact(str(path), tuple(config["timing_shape"]))
    if digest != timing.digest or scale != config["timing_scale"]:
        raise ValueError("LNN prepared timing bytes or scale are invalid")
    return values


def _validated_config(passport: ModelPassport, X: np.ndarray) -> dict:
    config = sealed_config(passport.architecture.config)
    validate_contract(passport, config, X)
    return config


def _load_scores(
    passport: ModelPassport, model_path: Path, config: dict,
    X: np.ndarray, timespans: np.ndarray | None,
) -> np.ndarray:
    loader = passport.inference.loader
    if loader == MLX_LOADER:
        from .adapters.mlx_identity import MLX_LIFECYCLE
        from .adapters.mlx_native import load_scores
        from .adapters.mlx_platform import require_mlx_platform
        require_mlx_platform()
        if (
            passport.architecture.architecture not in {"lstm", "tcn"}
            or passport.architecture.framework != MLX_LIFECYCLE.framework
            or passport.architecture.framework_version != MLX_LIFECYCLE.framework_version
            or passport.inference.version != MLX_LIFECYCLE.framework_version
            or version("mlx") != MLX_LIFECYCLE.framework_version
            or passport.model_artifact.format != MLX_LIFECYCLE.artifact_format
            or timespans is not None
        ):
            raise ValueError("MLX passport framework or loader contract is invalid")
        return load_scores(model_path, passport.architecture.architecture, config, X)
    if loader == "torch.state_dict":
        from .adapters.torch_native import load_scores
        if (
            passport.architecture.architecture not in {"lstm", "tcn"}
            or passport.architecture.framework != "torch"
            or passport.architecture.framework_version != version("torch")
            or passport.inference.version != version("torch")
            or passport.model_artifact.format != "pytorch" or timespans is not None
        ):
            raise ValueError("torch passport framework or loader contract is invalid")
        return load_scores(str(model_path), passport.architecture.architecture, config, X)
    if loader == LNN_LOADER:
        from .adapters.lnn_native import load_scores
        if (
            passport.architecture.architecture != "lnn"
            or passport.architecture.framework != "ncps"
            or passport.architecture.framework_version != version("ncps")
            or passport.inference.version != version("ncps")
            or passport.model_artifact.format != "pytorch" or timespans is None
        ):
            raise ValueError("LNN passport framework, loader, or timing contract is invalid")
        return load_scores(model_path, config, X, timespans)
    if loader == "transformers.patchtst":
        from .adapters.patchtst_native import load_scores
        if (
            passport.architecture.architecture != "patchtst"
            or passport.architecture.framework != "transformers"
            or passport.architecture.framework_version != version("transformers")
            or passport.inference.version != version("transformers")
            or passport.model_artifact.format != "transformers-patchtst"
            or timespans is not None
        ):
            raise ValueError("PatchTST passport framework or loader contract is invalid")
        return load_scores(model_path, config, X)
    if loader == "chronos.Chronos2Pipeline":
        from .adapters.chronos_native import load_scores
        if (
            passport.architecture.architecture != "chronos"
            or passport.architecture.framework != "chronos-forecasting"
            or passport.architecture.framework_version != version("chronos-forecasting")
            or passport.inference.version != version("chronos-forecasting")
            or passport.model_artifact.format != "chronos2-native-probe"
            or timespans is not None
        ):
            raise ValueError("Chronos passport framework or loader contract is invalid")
        return load_scores(model_path, config, X)
    raise ValueError("neural passport loader is not approved")


__all__ = ["load_neural_passport_scores"]

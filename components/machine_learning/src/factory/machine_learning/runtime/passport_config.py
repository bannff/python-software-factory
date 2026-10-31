"""Server-owned durable root configuration for ModelPassport operations."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .passport_paths import reject_symlink_ancestors

_ROOT_ENV = "ML_MODEL_PASSPORT_ROOT"
_MODEL_ROOT_ENV = "ML_LIGHTGBM_MODEL_ROOT"
_LNN_ROOT_ENV = "ML_LNN_MODEL_ROOT"


def configured_passport_root(explicit: str | Path | None = None) -> Path:
    """Return the mandatory durable trust root, failing loudly when absent."""
    value = str(explicit).strip() if explicit is not None else os.environ.get(_ROOT_ENV, "").strip()
    if not value:
        raise ValueError(f"{_ROOT_ENV} is required for ModelPassport operations")
    root = Path(value).expanduser().absolute()
    reject_symlink_ancestors(root)
    root.mkdir(parents=True, exist_ok=True)
    reject_symlink_ancestors(root)
    return root


def passport_training_paths(passport_root: str | Path) -> tuple[Path, Path]:
    """Return the trust root and its private CAN preparation directory."""
    root = configured_passport_root(passport_root)
    training = root / "keystone_snapshots"
    reject_symlink_ancestors(training)
    training.mkdir(parents=True, exist_ok=True)
    reject_symlink_ancestors(training)
    return root, training


def configured_lightgbm_root(explicit: str | Path | None = None) -> Path | None:
    """Resolve a test-injected or server-configured model root beneath trust root."""
    passport_value = os.environ.get(_ROOT_ENV, "").strip()
    configured = explicit or os.environ.get(_MODEL_ROOT_ENV)
    if explicit is None and not configured and passport_value:
        configured = configured_passport_root() / "models"
    if configured is None:
        return None
    model_root = Path(configured).expanduser().absolute()
    reject_symlink_ancestors(model_root)
    if passport_value:
        passport_root = configured_passport_root()
        try:
            model_root.relative_to(passport_root)
            model_root.resolve(strict=False).relative_to(passport_root.resolve())
        except ValueError as exc:
            raise ValueError(f"{_MODEL_ROOT_ENV} must be beneath {_ROOT_ENV}") from exc
    model_root.mkdir(parents=True, exist_ok=True)
    reject_symlink_ancestors(model_root)
    return model_root


def configured_lnn_root(explicit: str | Path | None = None) -> Path | None:
    """Resolve the dedicated LNN model root beneath passport authority."""
    passport_value = os.environ.get(_ROOT_ENV, "").strip()
    configured = explicit or os.environ.get(_LNN_ROOT_ENV)
    if explicit is None and not configured and passport_value:
        configured = configured_passport_root() / "models" / "lnn"
    if configured is None:
        return None
    root = Path(configured).expanduser().absolute()
    reject_symlink_ancestors(root)
    if passport_value:
        trust = configured_passport_root()
        try:
            root.relative_to(trust)
            root.resolve(strict=False).relative_to(trust.resolve())
        except ValueError as exc:
            raise ValueError(f"{_LNN_ROOT_ENV} must be beneath {_ROOT_ENV}") from exc
    root.mkdir(parents=True, exist_ok=True)
    reject_symlink_ancestors(root)
    return root


@dataclass(frozen=True)
class ChronosRoots:
    """Authoritative durable namespaces for Chronos acquisition and training."""

    trust_root: Path
    backbone_root: Path
    model_root: Path


def resolve_chronos_roots(storage_root: str | Path) -> ChronosRoots:
    """Resolve Chronos roots from an explicit durable passport authority."""
    if storage_root is None or not str(storage_root).strip():
        raise ValueError("Chronos requires an explicit non-null storage root")
    trust_root = configured_passport_root(storage_root)
    backbone_root = trust_root / "backbones" / "chronos-2"
    model_root = trust_root / "models" / "chronos-2"
    for root in (backbone_root, model_root):
        reject_symlink_ancestors(root)
        root.mkdir(parents=True, exist_ok=True)
        reject_symlink_ancestors(root)
    return ChronosRoots(trust_root, backbone_root, model_root)


__all__ = [
    "ChronosRoots", "configured_lightgbm_root", "configured_lnn_root",
    "configured_passport_root", "passport_training_paths", "resolve_chronos_roots",
]

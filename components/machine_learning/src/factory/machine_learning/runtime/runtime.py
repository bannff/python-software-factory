"""Experiment tracking, fine-tuning, and warm-inference runtime factory."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from factory.mcp_utils.runtime.tool_failure import SafeDiagnostic

from .passport_root_composition import capture_passport_root
from .ports import ExperimentTracker, FineTuningPort, TimeSeriesTrainingPort, TrackerHealth
from .adapters.checkpoint_store import CheckpointStore
from .finetuning_factory import FINETUNING_BACKENDS, create_finetuner
from .timeseries_factory import (
    TIMESERIES_BACKENDS, create_timeseries_trainer, mlx_runtime_kwargs,
    resolve_timeseries_backend,
)

logger = logging.getLogger(__name__)

_TRACKER_BACKENDS = ["memory", "mlflow", "tensorboard"]


class TrackingRuntime:
    """Factory for experiment tracker and fine-tuning adapters."""

    def __init__(
        self, config: dict[str, Any] | None = None, *, passport_service: Any = None,
    ) -> None:
        self._config = config or {}
        self._passport_service = passport_service
        self._chronos_storage_root = capture_passport_root(
            self._config, passport_service,
        )
        self._trackers: dict[str, ExperimentTracker] = {}
        self._finetuners: dict[str, FineTuningPort] = {}
        self._timeseries_trainers: dict[str, TimeSeriesTrainingPort] = {}
        self._checkpoint_store: CheckpointStore | None = None
        # Warm model cache; passport promotion remains the deployability authority.
        self._inference_registry: dict[str, dict[str, Any]] = {}
        self._inference_bridges: dict[str, Any] = {}
        # TimeGAN adapter is lazy-built on first access.
        self._timegan_adapter: Any = None

    def get_checkpoint_store(self) -> CheckpointStore:
        """Get or create the checkpoint store."""
        if self._checkpoint_store is None:
            base_path = self._config.get("checkpoint_path")
            self._checkpoint_store = CheckpointStore(base_path)
        return self._checkpoint_store

    def get_tracker(self, backend: str | None = None, **kwargs: Any) -> ExperimentTracker:
        """Get or create an experiment tracker adapter.

        Default backend resolves from ML_TRACKER_BACKEND (fallback memory);
        the MLflow backend inherits MLFLOW_TRACKING_URI when unset.
        """
        if backend is None:
            backend = os.environ.get("ML_TRACKER_BACKEND", "memory")
        if backend == "mlflow" and not kwargs:
            tracking_uri = os.environ.get(
                "MLFLOW_TRACKING_URI", self._config.get("mlflow_tracking_uri"),
            )
            if tracking_uri:
                kwargs["tracking_uri"] = tracking_uri
        key = f"{backend}:{hash(frozenset(kwargs.items()))}"
        if key not in self._trackers:
            self._trackers[key] = self._create_tracker(backend, **kwargs)
        return self._trackers[key]

    def _create_tracker(self, backend: str, **kwargs: Any) -> ExperimentTracker:
        if backend == "memory":
            from .adapters.memory_adapter import MemoryTracker
            return MemoryTracker(**kwargs)
        elif backend == "mlflow":
            from .adapters.mlflow_adapter import MLflowTracker
            return MLflowTracker(**kwargs)
        elif backend == "tensorboard":
            from .adapters.tensorboard_adapter import TensorBoardTracker
            return TensorBoardTracker(**kwargs)
        raise SafeDiagnostic(
            f"Unknown tracker backend: {backend}. Available: {self.available_backends()}"
        )

    def get_finetuner(self, backend: str = "memory", **kwargs: Any) -> FineTuningPort:
        """Get or create a fine-tuning adapter."""
        key = f"ft:{backend}:{hash(frozenset(kwargs.items()))}"
        if key not in self._finetuners:
            self._finetuners[key] = create_finetuner(
                backend, self.get_checkpoint_store(), self._config, **kwargs,
            )
        return self._finetuners[key]

    def chronos_storage_root(self) -> Path | None:
        """Return the durable passport authority captured at construction."""
        return self._chronos_storage_root

    def get_timeseries_trainer(
        self, backend: str | None = None, **kwargs: Any,
    ) -> TimeSeriesTrainingPort:
        """Get or create a time-series trainer (None → env → sklearn default)."""
        backend = resolve_timeseries_backend(backend)
        if backend == "mlx":
            kwargs = mlx_runtime_kwargs(self, kwargs)
        elif backend == "sklearn":
            if "model_root" not in kwargs:
                configured = self._config.get("lightgbm_model_root")
                if configured:
                    kwargs["model_root"] = Path(configured)
            if "lnn_model_root" not in kwargs:
                from .passport_config import configured_lnn_root
                kwargs["lnn_model_root"] = configured_lnn_root(self._config.get("lnn_model_root"))
            kwargs.setdefault("chronos_storage_root", self.chronos_storage_root())
        key = f"ts:{backend}:{hash(frozenset(kwargs.items()))}"
        if key not in self._timeseries_trainers:
            self._timeseries_trainers[key] = create_timeseries_trainer(
                self, backend, **kwargs
            )
        return self._timeseries_trainers[key]

    @property
    def timegan_adapter(self) -> Any:
        """Singleton TimeGAN adapter (lazy-built); torch import deferred for macOS OMP safety."""
        if self._timegan_adapter is None:
            from .adapters.timegan import TimeGANAdapter
            self._timegan_adapter = TimeGANAdapter(
                tracker=self.get_tracker("memory"),
                checkpoint_store=self.get_checkpoint_store(),
            )
        return self._timegan_adapter

    # -- warm inference cache ------------------------------------------

    def register_inference_model(
        self, model_id: str, model_path: str, *, can_id: str,
        contract_uri: str, contract_digest: str, model_type: str,
        loader_id: str, model_digest: str, threshold: float = 0.5,
        required_shape: tuple[int, int], required_width: int,
        passport_ref: dict[str, Any] | None = None,
        passport_root: str | None = None,
        prepared_x_digest: str | None = None,
        prepared_y_digest: str | None = None,
        materializer_config_digest: str | None = None,
        inference_adapter: str | None = None,
        inference_version: str | None = None,
    ) -> None:
        """Register an exact trained-model/feature-contract binding."""
        from .inference_registry import register_inference_model
        register_inference_model(
            self, model_id, model_path, can_id=can_id,
            contract_uri=contract_uri, contract_digest=contract_digest,
            model_type=model_type, loader_id=loader_id,
            model_digest=model_digest, threshold=threshold,
            required_shape=required_shape, required_width=required_width,
            passport_ref=passport_ref, passport_root=passport_root,
            prepared_x_digest=prepared_x_digest,
            prepared_y_digest=prepared_y_digest,
            materializer_config_digest=materializer_config_digest,
            inference_adapter=inference_adapter,
            inference_version=inference_version,
        )

    def get_public_inference_bridge(self, model_id: str):
        """Return a bridge only after exact passport retrieval and revalidation."""
        from .passport_inference import get_public_inference_bridge
        return get_public_inference_bridge(self, model_id)
    def get_inference_bridge(self, model_id: str):
        """Get or lazily build a CanInferenceBridge for ``model_id``."""
        from .inference_registry import get_inference_bridge
        return get_inference_bridge(self, model_id)

    def get_inference_model_info(self, model_id: str) -> dict[str, Any] | None:
        """Return registry metadata + feature importances for ``model_id``."""
        from .inference_registry import get_inference_model_info
        return get_inference_model_info(self, model_id)

    # -- health / metadata ---------------------------------------------

    def health_check(self) -> dict[str, TrackerHealth]:
        """Check health of all active trackers."""
        return {name: tracker.health_check() for name, tracker in self._trackers.items()}

    @staticmethod
    def available_backends() -> list[str]:
        """List available tracker backends."""
        return list(_TRACKER_BACKENDS)

    @staticmethod
    def available_finetuning_backends() -> list[str]:
        """List available fine-tuning backends."""
        return list(FINETUNING_BACKENDS)

    @staticmethod
    def available_timeseries_backends() -> list[str]:
        """List available time-series training backends."""
        return list(TIMESERIES_BACKENDS)


_runtime: TrackingRuntime | None = None


def get_runtime() -> TrackingRuntime:
    """Get the global tracking runtime."""
    global _runtime
    if _runtime is None:
        _runtime = TrackingRuntime()
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (for testing)."""
    global _runtime
    _runtime = None

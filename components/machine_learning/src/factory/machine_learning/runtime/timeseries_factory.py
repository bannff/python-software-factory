"""Time-series trainer backend factory (machine_learning.runtime).

Extracted from ``runtime.py`` to keep that file under the 200 LOC tenet.
Owns backend registration and default resolution for
:class:`TimeSeriesTrainingPort` adapters.

Default backend is ``sklearn`` — the real training path
(:class:`SklearnTimeSeriesAdapter`: LightGBM locally, lstm/tcn routed to
torch, timegan routed to the TimeGAN adapter). The ``memory`` adapter
fabricates seed-hash metrics and exists for tests only; it must be
requested explicitly. This closes the fake-data wiring where every MCP
tool and the keystone CAN pipeline silently trained on synthetic
metrics (bd:python-factory-zgg1x).

The ``mlx`` backend routes LSTM/TCN training to Apple's MLX framework
(GPU/Neural Engine acceleration on M-series Silicon). Set
``ML_TIMESERIES_BACKEND=mlx`` to select it; PyTorch remains the
fallback for every other value and the explicit ``torch`` path is
left untouched so non-MLX environments are unaffected.

Override with the ``ML_TIMESERIES_BACKEND`` environment variable.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from factory.mcp_utils.runtime.tool_failure import SafeDiagnostic

if TYPE_CHECKING:  # pragma: no cover
    from .ports import TimeSeriesTrainingPort
    from .runtime import TrackingRuntime

TIMESERIES_BACKENDS = ["memory", "torch", "mlx", "sklearn"]

_ENV_VAR = "ML_TIMESERIES_BACKEND"
_DEFAULT_BACKEND = "sklearn"


def resolve_timeseries_backend(backend: str | None = None) -> str:
    """Resolve the effective backend name.

    Explicit ``backend`` wins; else ``ML_TIMESERIES_BACKEND``; else
    ``sklearn``. Resolution happens BEFORE cache-key computation in
    ``TrackingRuntime.get_timeseries_trainer`` so ``None`` and the
    resolved name share one cache entry.
    """
    resolved = backend or os.environ.get(_ENV_VAR) or _DEFAULT_BACKEND
    if resolved not in TIMESERIES_BACKENDS:
        raise SafeDiagnostic(
            f"Unknown time-series backend: {resolved}. Available: {TIMESERIES_BACKENDS}"
        )
    return resolved


def mlx_runtime_kwargs(
    runtime: TrackingRuntime, kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Bind MLX storage only to the root captured by runtime composition."""
    if "storage_root" in kwargs:
        raise ValueError("MLX durable storage is captured only at runtime composition")
    return {**kwargs, "storage_root": runtime.chronos_storage_root()}


def create_timeseries_trainer(
    runtime: TrackingRuntime, backend: str, **kwargs: Any
) -> TimeSeriesTrainingPort:
    """Build a trainer adapter for a resolved backend name."""
    if backend == "memory":
        from .adapters.timeseries_training import MemoryTimeSeriesTrainingAdapter
        return MemoryTimeSeriesTrainingAdapter(**kwargs)
    if backend == "torch":
        from .adapters.torch_timeseries import TorchTimeSeriesAdapter
        return TorchTimeSeriesAdapter(tracker=runtime.get_tracker(), **kwargs)
    if backend == "mlx":
        from .adapters.mlx_timeseries import MlxTimeSeriesAdapter
        storage_root = kwargs.pop("storage_root", runtime.chronos_storage_root())
        return MlxTimeSeriesAdapter(
            storage_root=storage_root, tracker=runtime.get_tracker(), **kwargs,
        )
    if backend == "sklearn":
        from .adapters.sklearn_timeseries import SklearnTimeSeriesAdapter
        return SklearnTimeSeriesAdapter(
            tracker=runtime.get_tracker(),
            checkpoint_store=runtime.get_checkpoint_store(),
            **kwargs,
        )
    raise SafeDiagnostic(
        f"Unknown time-series backend: {backend}. Available: {TIMESERIES_BACKENDS}"
    )


# Per-model adapter registry: maps a TimeSeriesModelType to the
# adapter that knows how to train it. The :func:`create_model_adapter`
# factory is the single dispatch point used by the sklearn aggregator
# (and any future "all backends" entry points) to route a model_type
# string to the right concrete implementation. The default backend
# for transformer / recurrent / liquid architectures is PyTorch;
# add an ``"mlx"`` entry here when the MLX port is implemented.
_MODEL_ADAPTERS: dict[str, str] = {
    "patchtst": "patchtst_timeseries.PatchTSTTimeSeriesAdapter",
    "chronos": "chronos_timeseries.ChronosTimeSeriesAdapter",
    "lnn": "lnn_timeseries.LnnTimeSeriesAdapter",
}


def create_model_adapter(
    model_type: str, tracker: Any = None, checkpoint_store: Any = None,
    model_root: Any = None, lnn_model_root: Any = None,
    chronos_storage_root: Any = None,
) -> Any:
    """Build a model-specific trainer adapter (e.g. PatchTST, Chronos, LNN).

    Used by the sklearn aggregator to dispatch ``model_type="patchtst"``
    to the PatchTST adapter, ``model_type="chronos"`` to the Chronos
    adapter, and so on. Each adapter implements
    :class:`TimeSeriesTrainingPort` so the aggregator's caller doesn't
    have to branch.
    """
    if model_type not in _MODEL_ADAPTERS:
        raise ValueError(
            f"Unknown model_type: {model_type!r}. "
            f"Known: {sorted(_MODEL_ADAPTERS)}",
        )
    module_name, class_name = _MODEL_ADAPTERS[model_type].rsplit(".", 1)
    import importlib
    mod = importlib.import_module(f".adapters.{module_name}", package=__package__)
    cls = getattr(mod, class_name)
    kwargs = {"tracker": tracker, "checkpoint_store": checkpoint_store}
    if model_type == "chronos":
        kwargs["storage_root"] = chronos_storage_root
    elif model_type == "lnn":
        kwargs["model_root"] = lnn_model_root
    elif model_type == "patchtst":
        kwargs["model_root"] = model_root
    return cls(**kwargs)


def get_model_adapter_specs() -> dict[str, str]:
    """Return the ``model_type.value -> "module.ClassName"`` mapping.

    Single source of truth for which model types have a dedicated
    adapter. ``ModelAdapterRegistry`` uses this to answer ``has()``
    queries without constructing the adapter.
    """
    return dict(_MODEL_ADAPTERS)


__all__ = [
    "TIMESERIES_BACKENDS",
    "create_model_adapter",
    "create_timeseries_trainer",
    "get_model_adapter_specs",
    "resolve_timeseries_backend",
]

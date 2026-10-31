"""Experiment tracking and fine-tuning adapters.

Time-series adapters stay lazy so importing the brick does not require
optional ML dependencies such as Torch, joblib, or LightGBM. Import an
adapter explicitly when needed, or resolve it through
:func:`TrackingRuntime.get_timeseries_trainer`.
"""

from .memory_adapter import MemoryTracker
from .mlflow_adapter import MLflowTracker
from .tensorboard_adapter import TensorBoardTracker
from .memory_finetuning import MemoryFineTuningAdapter

__all__ = [
    "MemoryTracker",
    "MLflowTracker",
    "TensorBoardTracker",
    "MemoryFineTuningAdapter",
    # Exposed for type-checkers only; resolved lazily on import.
    "SklearnTimeSeriesAdapter",
    "TorchTimeSeriesAdapter",
    "PatchTSTTimeSeriesAdapter",
    "ChronosTimeSeriesAdapter",
    "LnnTimeSeriesAdapter",
]


def __getattr__(name: str):  # pragma: no cover - exercised indirectly
    """Lazy attribute access — defers torch/joblib imports until first use.

    ``SklearnTimeSeriesAdapter`` imports ``joblib`` at module level; an
    eager import here made the whole brick fail to lazy-load in
    environments without the optional ML extras (aggregator logged
    "Failed to lazy-load 'machine_learning': No module named 'joblib'").
    Same deferral rationale as ``TorchTimeSeriesAdapter`` above.
    """
    if name == "TorchTimeSeriesAdapter":
        from .torch_timeseries import TorchTimeSeriesAdapter
        return TorchTimeSeriesAdapter
    if name == "SklearnTimeSeriesAdapter":
        from .sklearn_timeseries import SklearnTimeSeriesAdapter
        return SklearnTimeSeriesAdapter
    if name == "TimeGANAdapter":
        from .timegan import TimeGANAdapter
        return TimeGANAdapter
    if name == "ConditionalTimeGANAdapter":
        from .timegan_conditional import ConditionalTimeGANAdapter
        return ConditionalTimeGANAdapter
    if name == "PatchTSTTimeSeriesAdapter":
        from .patchtst_timeseries import PatchTSTTimeSeriesAdapter
        return PatchTSTTimeSeriesAdapter
    if name == "ChronosTimeSeriesAdapter":
        from .chronos_timeseries import ChronosTimeSeriesAdapter
        return ChronosTimeSeriesAdapter
    if name == "LnnTimeSeriesAdapter":
        from .lnn_timeseries import LnnTimeSeriesAdapter
        return LnnTimeSeriesAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

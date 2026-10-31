"""Per-model adapter registry and dispatch helper.

Maps each :class:`TimeSeriesModelType` to its dedicated training
adapter (e.g. PatchTST, Chronos, LNN) and exposes a small
:class:`ModelAdapterRegistry` class that lazily constructs each
adapter the first time it's needed. The sklearn aggregator uses
this to dispatch transformer / liquid architectures without
re-implementing the import dance.

The source of truth for which model types have a dedicated adapter
lives in :mod:`timeseries_factory` — this module just provides the
registry class and the model-set constants used by the sklearn
aggregator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..ports import TimeSeriesModelType

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

# Models routed to the PyTorch adapter (lstm / tcn).
TORCH_MODELS: set[TimeSeriesModelType] = {TimeSeriesModelType.lstm, TimeSeriesModelType.tcn}

# Generative models (unsupervised; no y_uri). Routed to TimeGAN adapter.
GENERATIVE_MODELS: set[TimeSeriesModelType] = {TimeSeriesModelType.timegan}


class ModelAdapterRegistry:
    """Lazy per-model adapter registry backed by ``timeseries_factory``.

    Each adapter is constructed on first access via
    :func:`factory.machine_learning.runtime.timeseries_factory.create_model_adapter`
    so importing the sklearn aggregator never pays the cost of
    importing torch / mlx unless a transformer / liquid model is
    actually trained.
    """

    def __init__(
        self, tracker: "Any" = None, checkpoint_store: "Any" = None,
        model_root: "Any" = None, lnn_model_root: "Any" = None,
        chronos_storage_root: "Any" = None,
    ) -> None:
        self._tracker = tracker
        self._checkpoint_store = checkpoint_store
        self._model_root = model_root
        self._lnn_model_root = lnn_model_root
        self._chronos_storage_root = chronos_storage_root
        self._cache: dict[TimeSeriesModelType, "Any"] = {}

    def has(self, model_type: "TimeSeriesModelType | str") -> bool:
        """Return True if a dedicated adapter exists for ``model_type``.

        Accepts either a :class:`TimeSeriesModelType` enum value or a
        raw string — the caller's train loop may be passing either
        depending on whether the entry point did the enum conversion.
        """
        from ..timeseries_factory import get_model_adapter_specs
        key = model_type.value if hasattr(model_type, "value") else model_type
        return key in get_model_adapter_specs()

    def get(self, model_type: TimeSeriesModelType) -> "Any":
        """Construct (or return cached) adapter for ``model_type``."""
        if model_type not in self._cache:
            from ..timeseries_factory import create_model_adapter
            self._cache[model_type] = create_model_adapter(
                model_type.value, tracker=self._tracker,
                checkpoint_store=self._checkpoint_store,
                model_root=self._model_root, lnn_model_root=self._lnn_model_root,
                chronos_storage_root=self._chronos_storage_root,
            )
        return self._cache[model_type]

    def iter_adapters(self) -> list["Any"]:
        """Return all lazy-built adapters (used by get / list fallthrough)."""
        return list(self._cache.values())


__all__ = [
    "GENERATIVE_MODELS",
    "ModelAdapterRegistry",
    "TORCH_MODELS",
]

"""Context correlation stage for the CAN failure-prediction pipeline.

Runs after ``context_augment`` and computes an analytical sidecar describing
how each context feature (temperature, aggressiveness, mileage, ...) correlates
with each failure mode in the context-enriched CAN record stream. The sidecar
is retained for analysis; it never becomes synthesis input or drives corpus
sampling or augmentation.

Three correlation methods are supported (recipe-selectable via
``method``):

* ``pearson``            — linear correlation via ``numpy.corrcoef``.
* ``spearman``           — rank correlation. Ranks are computed in
  pure numpy with ``argsort`` to avoid a scipy dependency.
* ``mutual_information`` — 10-bin binned MI in pure numpy
  (``np.histogram2d`` + the standard I(X;Y) formula).

The adapter is a sidecar: it never mutates its input records.
Every input record is yielded unchanged, then a single trailing
``context_correlation_heatmap`` record is emitted. Records are
paired by their natural order, so upstream stages should align
context windows with CAN windows (matching ``vehicle_id`` and
``window_start``) before this stage runs.

Math primitives (matrix construction, Pearson / Spearman / MI)
live in :mod:`_context_correlate_helpers` to keep this file
under the 200-LOC factory ceiling.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any

import numpy as np

from ._context_correlate_helpers import (
    build_context_matrix,
    build_failure_matrix,
    compute_correlation,
)

# Defaults chosen to match the spec's canonical examples
# (``temp_c`` ~ -0.82 with battery_degradation etc.).
DEFAULT_METHOD: str = "pearson"
DEFAULT_MIN_CORRELATION: float = 0.3


class ContextCorrelateStageAdapter:
    """Adapter that emits a context↔failure-mode correlation heatmap.

    Implements :class:`factory.dataset.runtime.ports.DatasetStagePort`
    so it slots into the recipe stage map alongside the other CAN
    adapters. ``name`` matches the recipe stage ID; ``stage_version``
    is a stable identifier for checkpoint lineage.
    """

    name = "context_correlate"
    stage_version = "factory-context-correlate-1"
    allowed_config = frozenset({
        "method", "min_correlation", "input_uri",
        "context_features", "failure_modes",
        "context_field", "failure_field",
    })

    def execute(
        self,
        records: Iterable[Any],
        config: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every record unchanged, then one JSON-safe heatmap sidecar."""
        values = dict(config or {})
        unknown = set(values) - self.allowed_config
        if unknown:
            raise ValueError(
                f"Unsupported context_correlate configuration: {sorted(unknown)}"
            )

        method = str(values.get("method", DEFAULT_METHOD)).lower()
        if method not in ("pearson", "spearman", "mutual_information"):
            raise ValueError(f"Unsupported correlation method: {method!r}")
        min_corr = float(values.get("min_correlation", DEFAULT_MIN_CORRELATION))
        context_features = list(values.get("context_features") or [])
        failure_modes = list(values.get("failure_modes") or [])
        if not context_features:
            raise ValueError(
                "context_correlate requires non-empty 'context_features'"
            )
        if not failure_modes:
            raise ValueError(
                "context_correlate requires non-empty 'failure_modes'"
            )
        context_field = str(values.get("context_field", "context"))
        failure_field = str(values.get("failure_field", "failure_mode"))

        record_list = list(records)
        input_uri = values.get("input_uri")
        if not record_list and input_uri:
            from ..helpers import load_records_from_uri
            record_list = load_records_from_uri(input_uri)
        # Pass-through: every record is preserved bit-for-bit.
        for rec in record_list:
            yield rec
        if not record_list:
            return

        # Build the (N x F) context matrix and (N x M) binary failure
        # indicator matrix. NaN in the context matrix is dropped
        # per-pair so a missing weather field doesn't poison the
        # whole correlation pass.
        ctx_mat = build_context_matrix(record_list, context_features, context_field)
        fail_mat = build_failure_matrix(record_list, failure_modes, failure_field)

        heatmap: list[dict[str, Any]] = []
        for i, feature in enumerate(context_features):
            for j, mode in enumerate(failure_modes):
                x = ctx_mat[:, i]
                y = fail_mat[:, j]
                mask = np.isfinite(x)
                if int(mask.sum()) < 2:
                    continue
                r = compute_correlation(x[mask], y[mask], method)
                if r is None:
                    continue
                # Pearson / Spearman are signed; MI is non-negative.
                # Threshold applies to |r| for the signed methods and
                # to r itself for MI.
                score = abs(r) if method in ("pearson", "spearman") else r
                if score < min_corr:
                    continue
                heatmap.append({
                    "context_feature": feature,
                    "failure_mode": mode,
                    "correlation": round(float(r), 4),
                    "method": method,
                })

        yield {
            "record_type": "context_correlation_heatmap",
            "method": method,
            "min_correlation": min_corr,
            "n_records": len(record_list),
            "context_features": context_features,
            "failure_modes": failure_modes,
            "heatmap": heatmap,
        }


__all__ = [
    "ContextCorrelateStageAdapter",
    "DEFAULT_METHOD",
    "DEFAULT_MIN_CORRELATION",
]

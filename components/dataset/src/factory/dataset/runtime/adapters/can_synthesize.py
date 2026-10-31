"""Synthetic CAN data generation (Epic 3 + Phases 4, 5).

Stage 3 of the CAN failure-prediction pipeline. Fits an SDV synthesizer
(GaussianCopula or CTGAN) per CAN ID, clamps to constraint bounds, and
optionally applies temporal smoothing before synthesis.

Phase 4 wires the SCANIA pattern extractor + conditional TimeGAN
into the failure-injection layer:

* ``scania_data_uri``    — directory of SCANIA APS CSVs (train fresh)
* ``scania_model_id``    — reuse a cached conditional TimeGAN checkpoint
* ``injection_strategy`` — ``"rule"`` (default), ``"learned"``, ``"hybrid"``

Phase 5 adds correlation-based failure injection for physically-
realistic coupled-signal faults with gradual onset/decay:

* ``injection_strategy="correlation"`` — uses the per-CAN-ID
  ``correlations`` from ``can_profile`` (or an explicit
  ``correlation_matrix`` / ``correlation_matrix_uri``) to corrupt
  multiple coupled signals together with a smooth envelope.
* ``onset_frames`` / ``decay_frames`` — length of the smooth ramp
  on each side of the failure window.

The SDV-specific helpers (fit_and_sample, smooth_signals,
clamp_to_constraints, build_records) live in
``can_synthesize_helpers.py``; the per-CAN-ID dispatch lives in
``_can_synthesize_dispatch.py``; the hybrid training wiring lives
in ``can_synthesize_hybrid_helpers.py``; URI loading for the
correlation matrix lives in ``can_synthesize_uri_helpers.py``.
This keeps the adapter under the <200 LOC file limit.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from typing import Any

import numpy as np

from ._can_synthesize_dispatch import dispatch_per_can_id
from ._can_synthesize_patterns import apply_configured_patterns
from .can_synthesize_hybrid_helpers import build_hybrid_sampler
from .can_synthesize_uri_helpers import load_correlation_matrix_from_uri
from .failure_injection import (
    DEFAULT_DECAY_FRAMES,
    DEFAULT_ONSET_FRAMES,
)


class CanSynthesizeStageAdapter:
    """Multiplies CAN records into a labeled training corpus (DatasetStagePort)."""

    name = "can_synthesize"
    stage_version = "factory-can-synthesize-1"
    allowed_config = frozenset({
        "multiplier", "failure_rate", "failure_modes", "seed",
        "constraint_schema", "vehicle_id", "input_uri",
        "method", "temporal_smoothing_sigma",
        # Phase 4: SCANIA → conditional TimeGAN → hybrid failure injection.
        "scania_data_uri", "scania_model_id", "injection_strategy",
        # Phase 5: correlation-based physically-realistic injection.
        "correlation_matrix", "correlation_matrix_uri",
        "onset_frames", "decay_frames",
        # Context-aware synthesis: condition failures on environment
        # context, attach a correlation heatmap, and pass through named
        # context features to the failure-injection layer.
        "context_conditioned_failure",  # bool
        "context_correlation_heatmap",  # dict
        "context_features",  # list
        # Evidence-backed semantic failure patterns (additive, opt-in).
        "failure_pattern_refs", "failure_scenario_refs", "dbc_definition",
    })

    def execute(
        self,
        records: Iterable[Any],
        config: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield synthesized CAN frame records with failure-mode labels."""
        values = dict(config or {})
        unknown = set(values) - self.allowed_config
        if unknown:
            raise ValueError(
                f"Unsupported can_synthesize configuration: {sorted(unknown)}"
            )

        params = _parse_config_params(values)
        # Phase 5: explicit matrix wins over URI, which wins over
        # auto-extraction from the constraint schema.
        global_matrix = values.get("correlation_matrix")
        if global_matrix is None:
            uri = values.get("correlation_matrix_uri")
            if uri:
                global_matrix = load_correlation_matrix_from_uri(uri)
        # Phase 4: resolve the learned sampler (None → pure rule mode)
        # and auto-promote "rule" to "hybrid" when a sampler exists.
        learned_sampler = build_hybrid_sampler(
            scania_data_uri=values.get("scania_data_uri"),
            scania_model_id=values.get("scania_model_id"),
            seed=params["seed"],
        )
        if learned_sampler is not None and params["injection_strategy"] == "rule":
            params["injection_strategy"] = "hybrid"
        # Standalone mode: load records from input_uri if empty.
        record_list = list(records)
        if not record_list and params["input_uri"]:
            record_list = _load_records_from_uri(params["input_uri"])
        generated_params = dict(params)
        pattern_refs = list(values.get("failure_pattern_refs") or [])
        if pattern_refs:
            generated_params["failure_rate"] = 0.0
        generated = list(_dispatch_synthesize(
            record_list, generated_params, learned_sampler, global_matrix,
        ))
        if pattern_refs:
            generated = apply_configured_patterns(
                generated, pattern_refs, values.get("dbc_definition") or {}, params["seed"],
                params["constraint_schema"], list(values.get("failure_scenario_refs") or []),
            )
        return iter(generated)


def _parse_config_params(values: dict[str, Any]) -> dict[str, Any]:
    """Validate config and return a flat dict of normalized params.

    The flat shape keeps the dispatch helper free of mixed
    Mapping/None gymnastics and makes the validation surface
    auditable in one place.
    """
    multiplier = int(values.get("multiplier", 10))
    failure_rate = float(values.get("failure_rate", 0.1))
    seed = int(values.get("seed", 42))
    if multiplier < 1:
        raise ValueError("multiplier must be >= 1")
    if not 0.0 <= failure_rate <= 1.0:
        raise ValueError("failure_rate must be in [0, 1]")
    return {
        "multiplier": multiplier,
        "failure_rate": failure_rate,
        "seed": seed,
        "failure_modes": tuple(values.get("failure_modes") or ()),
        "constraint_schema": values.get("constraint_schema") or {},
        "vehicle_id": values.get("vehicle_id", "synthetic"),
        "input_uri": values.get("input_uri"),
        "method": str(values.get("method", "gaussian_copula")),
        "smoothing_sigma": float(values.get("temporal_smoothing_sigma", 0)),
        "injection_strategy": str(values.get("injection_strategy", "rule")),
        "onset_frames": max(0, int(values.get("onset_frames", DEFAULT_ONSET_FRAMES))),
        "decay_frames": max(0, int(values.get("decay_frames", DEFAULT_DECAY_FRAMES))),
        # Context-aware synthesis: when ``context_conditioned_failure``
        # is True the failure-injection layer biases mode selection by
        # the per-frame context (see ``context_correlate`` heatmap and
        # ``context_features`` allowlist).
        "context_conditioned": bool(values.get("context_conditioned_failure", False)),
        "context_heatmap": values.get("context_correlation_heatmap") or {},
        "context_features": list(values.get("context_features") or []),
    }


def _load_records_from_uri(uri: str) -> list[dict[str, Any]]:
    """Load CAN frame records from a file:// URI (JSONL)."""
    from ..helpers import load_records_from_uri
    return load_records_from_uri(uri)


def _dispatch_synthesize(
    record_list: list[dict[str, Any]],
    params: dict[str, Any],
    learned_sampler: Any,
    global_matrix: Any,
) -> Iterator[dict[str, Any]]:
    """Group records by CAN ID and yield synthesized streams per ID."""
    by_can_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in record_list:
        if rec.get("decoded_signals"):
            by_can_id[rec["arbitration_id"]].append(rec)
    if not by_can_id:
        return iter(())
    constraint_schema = params["constraint_schema"]
    can_ids_meta = constraint_schema.get("can_ids") or {}
    rng = np.random.default_rng(params["seed"])
    for arb_id, group in by_can_id.items():
        # Per-CAN-ID matrix: prefer the explicit global, otherwise
        # fall back to the ``correlations`` field that ``can_profile``
        # emits in the constraint schema.
        per_id_constraints = can_ids_meta.get(arb_id, {})
        matrix = global_matrix
        if matrix is None:
            matrix = per_id_constraints.get("correlations")
        yield from dispatch_per_can_id(
            arb_id=arb_id, group=group, constraints=per_id_constraints,
            params=params, rng=rng, learned_sampler=learned_sampler,
            correlation_matrix=matrix,
        )

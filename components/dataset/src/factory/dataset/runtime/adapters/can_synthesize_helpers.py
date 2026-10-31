"""SDV-specific synthesis helpers for the CAN pipeline.

Split from ``can_synthesize.py`` to keep the main adapter under the
<200 LOC limit. These helpers handle:

* ``_fit_and_sample`` — fit an SDV model and draw a synthetic matrix
  with every column forced to ``numerical`` (the auto-detection
  otherwise flips boolean-like signals to ``categorical`` and the
  sampler returns string labels).
* ``_smooth_signals`` — optional Gaussian smoothing of the per-arb
  group before fitting.
* ``_clamp_to_constraints`` — apply [min, max] bounds from the
  constraint schema.
* ``_build_records`` — reconstruct canonical ``can_frame`` records
  from the synthetic signal matrix.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np


def fit_and_sample(
    df: "pd.DataFrame",
    n_samples: int,
    *,
    sdv_seed: int,
    method: str = "gaussian_copula",
) -> np.ndarray:
    """Fit an SDV synthesizer and return ``n_samples`` synthetic rows.

    We force every signal column to ``sdtype='numerical'`` because
    SDV's auto-detection can flip boolean-like or low-cardinality
    signals to ``categorical``, and then at sample time the model
    returns string category labels instead of the underlying numeric
    code. For our pipeline every ``decoded_signals`` value is numeric
    by construction (see ``CanIngestStageAdapter._try_decode`` and
    ``MultiDbcDecoder.try_decode`` which always cast to ``float``).
    """
    from sdv.metadata import Metadata

    metadata = Metadata()
    metadata.detect_table_from_dataframe(table_name="data", data=df)
    for col in df.columns:
        # SDV's auto-detection flips boolean-like / low-cardinality
        # signals to ``categorical`` and the sampler then returns
        # string category labels. It also flags unique-valued
        # columns as ``id`` and registers them as the table's
        # primary_key, which then fails validation when we flip
        # them back to ``numerical``. Force every signal to
        # ``numerical`` and clear the table-level key fields. The
        # input data is already ``float``-only by construction
        # (see ``CanIngestStageAdapter._try_decode`` and
        # ``MultiDbcDecoder.try_decode``).
        metadata.tables["data"].columns[col] = {"sdtype": "numerical"}
    metadata.tables["data"].primary_key = None
    metadata.tables["data"].alternate_keys = []
    metadata.tables["data"].sequence_key = None
    metadata.tables["data"].sequence_index = None
    if method == "ctgan":
        from sdv.single_table import CTGANSynthesizer
        model = CTGANSynthesizer(metadata, epochs=300, batch_size=500, verbose=False)
    else:
        from sdv.single_table import GaussianCopulaSynthesizer
        model = GaussianCopulaSynthesizer(metadata)
    model.fit(df)
    model._set_random_state(sdv_seed)
    sampled = model.sample(n_samples).to_numpy()
    # Belt and braces: coerce to float; non-numeric cells become NaN
    # rather than raising on downstream float casts.
    return np.array(
        [[float(v) if v == v else float("nan") for v in row] for row in sampled],
        dtype=float,
    )


def smooth_signals(
    group: list[dict[str, Any]], sigma: float
) -> list[dict[str, Any]]:
    """Apply Gaussian smoothing to signal values across consecutive frames."""
    if sigma <= 0 or len(group) < 3:
        return group
    signal_names = sorted({n for r in group for n in (r.get("decoded_signals") or {})})
    kernel_size = max(3, int(sigma * 6) | 1)
    x = np.arange(kernel_size) - kernel_size // 2
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel /= kernel.sum()
    for name in signal_names:
        vals = np.array(
            [float((r.get("decoded_signals") or {}).get(name, 0.0)) for r in group]
        )
        padded = np.pad(vals, (kernel_size // 2, kernel_size // 2), mode="edge")
        smoothed = np.convolve(padded, kernel, mode="valid")[: len(vals)]
        for r, v in zip(group, smoothed):
            if r.get("decoded_signals") and name in r["decoded_signals"]:
                r["decoded_signals"][name] = float(v)
    return group


def clamp_to_constraints(
    values: np.ndarray,
    signal_meta: dict[str, dict[str, Any]],
    signal_names: list[str],
) -> np.ndarray:
    """Clamp each column to [min, max] from the constraint schema."""
    clamped = values.astype(float, copy=True)
    for j, name in enumerate(signal_names):
        meta = signal_meta.get(name) or {}
        lo, hi = meta.get("min"), meta.get("max")
        if lo is not None:
            clamped[:, j] = np.maximum(clamped[:, j], float(lo))
        if hi is not None:
            clamped[:, j] = np.minimum(clamped[:, j], float(hi))
    return clamped


def build_records(
    *,
    template: dict[str, Any],
    donors: list[dict[str, Any]],
    arb_id: str,
    signal_names: list[str],
    values: np.ndarray,
    period_ns: int,
    vehicle_id: str,
) -> list[dict[str, Any]]:
    """Reconstruct CAN frames with deterministic donor context and lineage."""
    base_ts = int(template.get("timestamp_ns") or 0)
    trip_root = template.get("trip_id", "unknown")
    ordered_donors = sorted(
        donors, key=lambda item: (int(item.get("timestamp_ns", 0)), str(item.get("trip_id", ""))),
    )
    out: list[dict[str, Any]] = []
    for i in range(values.shape[0]):
        donor = ordered_donors[i % len(ordered_donors)]
        decoded = {n: float(values[i, j]) for j, n in enumerate(signal_names)}
        source_lineage = deepcopy(donor.get("source_lineage") or [{
            "timestamp_ns": donor.get("timestamp_ns"),
            "trip_id": donor.get("trip_id"),
            "arbitration_id": donor.get("arbitration_id"),
            "capture_source": donor.get("capture_source"),
        }])
        synthetic_lineage = list(deepcopy(donor.get("synthetic_lineage") or []))
        synthetic_lineage.append({
            "method": "sdv", "synthetic_row": i,
            "donor_timestamp_ns": donor.get("timestamp_ns"),
        })
        rec: dict[str, Any] = {
            "timestamp_ns": base_ts + i * period_ns,
            "vehicle_id": vehicle_id,
            "trip_id": f"synth_{trip_root}_{arb_id}",
            "bus_name": template.get("bus_name", "CAN1"),
            "arbitration_id": arb_id,
            "is_extended": bool(template.get("is_extended", False)),
            "is_fd": bool(template.get("is_fd", False)),
            "dlc": int(template.get("dlc", 8)),
            "data_bytes": template.get("data_bytes", "00" * 8),
            "frame_type": "data", "error_state": "normal",
            "source_ecu": template.get("source_ecu"),
            "capture_source": "synthetic", "decoded_signals": decoded,
            "dbc_message_name": template.get("dbc_message_name"),
            "dbc_definition_id": template.get("dbc_definition_id"),
            "dbc_catalog_id": template.get("dbc_catalog_id"),
            "dbc_version": template.get("dbc_version"),
            "dbc_digest": template.get("dbc_digest"),
            "dbc_source_uri": template.get("dbc_source_uri"),
            "dbc_artifact_uri": template.get("dbc_artifact_uri"),
            "dbc_source_kind": template.get("dbc_source_kind"),
            "dbc_spdx_license": template.get("dbc_spdx_license"),
            "dbc_retrieved_at": template.get("dbc_retrieved_at"),
            "dbc_parser_name": template.get("dbc_parser_name"),
            "dbc_parser_version": template.get("dbc_parser_version"),
            "dbc_validation_status": template.get("dbc_validation_status"),
            "dbc_provenance": deepcopy(template.get("dbc_provenance")),
            "decoded_signal_definitions": deepcopy(
                template.get("decoded_signal_definitions") or []
            ),
            "context": deepcopy(donor.get("context") or {}),
            "context_provenance": deepcopy(donor.get("context_provenance") or {}),
            "source_lineage": source_lineage,
            "synthetic_lineage": synthetic_lineage,
            "is_failure": 0, "failure_mode": None,
            "failure_timestamp_ns": None,
        }
        out.append(rec)
    return out

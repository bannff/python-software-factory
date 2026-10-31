"""CAN signal profiling & edge-mapping for the CAN failure-prediction pipeline.

Stage 2 of the CAN ingest pipeline. Consumes canonical ``can_frame``
records from ``CanIngestStageAdapter`` and emits a constraint schema for
downstream failure-injection generators.

Per-signal statistics (min/max/mean/std/delta_max) bound mutations, while
Pearson correlations preserve coupled dynamics between signals on the same
CAN ID. ``window_ms`` is accepted for future time-windowed analysis.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from typing import Any


class CanProfileStageAdapter:
    """Adapter that profiles decoded CAN signals into a constraint schema.

    Implements ``DatasetStagePort`` so it slots into the recipe stage map
    immediately after ``can_ingest``.
    """

    name = "can_profile"
    stage_version = "factory-can-profile-1"
    allowed_config = frozenset({"window_ms", "correlation_threshold", "input_uri"})

    def execute(
        self,
        records: Iterable[Any],
        config: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield a single constraint schema dict derived from decoded signals."""
        values = dict(config or {})
        unknown = set(values) - self.allowed_config
        if unknown:
            raise ValueError(f"Unsupported can_profile configuration: {sorted(unknown)}")

        correlation_threshold = float(values.get("correlation_threshold", 0.7))
        # window_ms is reserved for future time-windowed correlation analysis.
        _ = int(values.get("window_ms", 10))

        # When run standalone, load records from input_uri if the
        # records iterable is empty (materializer sets records=[] for
        # can_frame schema recipes).
        record_list = list(records)
        input_uri = values.get("input_uri")
        if not record_list and input_uri:
            record_list = _load_records_from_uri(input_uri)

        by_can_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        all_timestamps_ns: list[int] = []
        total_records = 0
        for record in record_list:
            total_records += 1
            all_timestamps_ns.append(int(record["timestamp_ns"]))
            if record.get("decoded_signals") is None:
                continue
            by_can_id[record["arbitration_id"]].append(record)

        # Pre-compute the global recording time span. We use this for every
        # per-CAN-ID rate so that bursty IDs (e.g. errors captured in a single
        # microsecond) don't produce nonsensical kHz/MHz rates.
        if all_timestamps_ns:
            global_min = min(all_timestamps_ns)
            global_max = max(all_timestamps_ns)
            global_span_s = max((global_max - global_min) / 1e9, 1e-9)
        else:
            global_min = global_max = 0
            global_span_s = 1e-9

        can_ids_schema: dict[str, dict[str, Any]] = {}
        total_signals = 0
        total_decoded_frames = 0

        for arb_id, group in sorted(by_can_id.items()):
            signals = _profile_signals(group)
            correlations = _compute_correlations(
                group, signals.keys(), threshold=correlation_threshold
            )

            can_ids_schema[arb_id] = {
                "message_name": _pick_message_name(group),
                "frame_rate_hz": round(len(group) / global_span_s, 2),
                "frame_count": len(group),
                "signals": signals,
                "correlations": correlations,
            }
            total_signals += len(signals)
            total_decoded_frames += len(group)

        yield {
            "version": "1",
            "can_ids": can_ids_schema,
            "summary": {
                "total_can_ids": len(can_ids_schema),
                "total_signals": total_signals,
                # ``total_frames`` reports the full capture size (raw + decoded)
                # so the summary mirrors the upstream record stream.
                "total_frames": total_records,
                "time_span_seconds": round(global_span_s, 2),
            },
        }


def _load_records_from_uri(uri: str) -> list[dict[str, Any]]:
    """Load CAN frame records from a file:// URI (JSONL)."""
    from ..helpers import load_records_from_uri
    return load_records_from_uri(uri)


def _to_float(value: Any) -> float | None:
    """Coerce a decoded signal value to float; return None if non-numeric."""
    if value is None:
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _pick_message_name(group: list[dict[str, Any]]) -> str | None:
    """Return the dominant DBC message name for a group of frames."""
    names = {g.get("dbc_message_name") for g in group if g.get("dbc_message_name")}
    if not names:
        return None
    return sorted(names)[0]


def _profile_signals(group: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Compute per-signal static boundaries and delta thresholds."""
    series: dict[str, list[float | None]] = defaultdict(list)
    for record in group:
        decoded = record.get("decoded_signals") or {}
        for name, raw in decoded.items():
            series[name].append(_to_float(raw))

    signals: dict[str, dict[str, Any]] = {}
    for name, values in series.items():
        numeric = [v for v in values if v is not None]
        if not numeric:
            continue
        vmin = min(numeric)
        vmax = max(numeric)
        vmean = sum(numeric) / len(numeric)
        vstd = 0.0
        if len(numeric) > 1:
            vstd = math.sqrt(sum((v - vmean) ** 2 for v in numeric) / len(numeric))
        delta_max = 0.0
        for prev, curr in zip(numeric, numeric[1:]):
            d = abs(curr - prev)
            if d > delta_max:
                delta_max = d
        signals[name] = {
            "min": vmin,
            "max": vmax,
            "mean": round(vmean, 6),
            "std": round(vstd, 6),
            "null_count": len(values) - len(numeric),
            "delta_max": round(delta_max, 6),
        }
    return signals


def _compute_correlations(
    group: list[dict[str, Any]],
    signal_names: Iterable[str],
    *,
    threshold: float,
) -> list[tuple[str, str, float]]:
    """Pearson correlations for signal pairs with |r| >= threshold."""
    names = list(signal_names)
    if len(names) < 2:
        return []

    series: dict[str, list[float | None]] = {n: [] for n in names}
    for record in group:
        decoded = record.get("decoded_signals") or {}
        for n in names:
            series[n].append(_to_float(decoded.get(n)))

    pairs: list[tuple[str, str, float]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            xs, ys = series[names[i]], series[names[j]]
            paired = [
                (a, b) for a, b in zip(xs, ys) if a is not None and b is not None
            ]
            if len(paired) < 2:
                continue
            x_vals = [p[0] for p in paired]
            y_vals = [p[1] for p in paired]
            mx = sum(x_vals) / len(x_vals)
            my = sum(y_vals) / len(y_vals)
            sx = math.sqrt(sum((a - mx) ** 2 for a in x_vals))
            sy = math.sqrt(sum((b - my) ** 2 for b in y_vals))
            if sx == 0 or sy == 0:
                continue
            num = sum((a - mx) * (b - my) for a, b in zip(x_vals, y_vals))
            r = num / (sx * sy)
            if abs(r) >= threshold:
                pairs.append((names[i], names[j], round(r, 3)))
    return pairs

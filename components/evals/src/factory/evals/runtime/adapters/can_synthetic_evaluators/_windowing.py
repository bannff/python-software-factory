"""Windowed CAN record -> per-signal value series.

A windowed record is a dict ``{"window_data": <2D>, "signal_names": [...]}``
where ``window_data`` has shape (T, S) — T time steps and S signals.

These helpers extract a 1D value series per signal by aggregating
the time axis per window (default: mean) and concatenating the
per-window values across all windows.
"""

from __future__ import annotations


def is_windowed(records: list) -> bool:
    """True if records are windowed (first element is a dict with window_data)."""
    return bool(records) and isinstance(records[0], dict) and "window_data" in records[0]


def window_to_per_signal(
    records: list, agg: str = "mean"
) -> dict[str, list[float]]:
    """Aggregate windowed records to one value per (window, signal).

    For each window, collapse the time axis with mean/sum/last so a
    record becomes a single value per signal. Then concatenate
    per-window values across windows to form a 1D series per
    signal. Returns {signal_name: [values...]} for the union of
    signal names across records (insertion order).
    """
    if not records:
        return {}
    seen: set[str] = set()
    names: list[str] = []
    for r in records:
        for nm in r.get("signal_names", []):
            if nm not in seen:
                seen.add(nm)
                names.append(nm)
    out: dict[str, list[float]] = {nm: [] for nm in names}
    for r in records:
        data = r.get("window_data")
        sn = r.get("signal_names", [])
        if data is None or not sn:
            continue
        try:
            T = len(data)
        except TypeError:
            continue
        if T == 0:
            continue
        for si, nm in enumerate(sn):
            try:
                ts = [float(data[t][si]) for t in range(T)]
            except (IndexError, TypeError):
                continue
            if not ts:
                continue
            if agg == "sum":
                v: float = sum(ts)
            elif agg == "last":
                v = ts[-1]
            else:
                v = sum(ts) / len(ts)
            out[nm].append(v)
    return out


__all__ = ["is_windowed", "window_to_per_signal"]

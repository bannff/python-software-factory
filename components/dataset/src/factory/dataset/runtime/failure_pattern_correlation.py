"""Typed adapter to the existing profile-driven correlation injector."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .adapters._correlation_injection_helpers import apply_correlation_failure
from .dbc_semantics import SemanticRoleBinding


@dataclass(frozen=True)
class CorrelationCandidate:
    record_index: int
    role: str
    value: float


def correlation_candidates(
    output: list[dict[str, Any]], roles: tuple[str, ...],
    role_map: dict[str, SemanticRoleBinding],
    correlations: tuple[tuple[str, str, float], ...],
    start: float, end: float, severity: float, parameters: dict[str, float],
    event_id: str, seed: int,
) -> tuple[CorrelationCandidate, ...]:
    """Run the established correlation injector and return constrained candidates."""
    names = {role_map[role].signal_name for role in roles}
    matrix = tuple(item for item in correlations
                   if item[0] in names and item[1] in names)
    if not matrix:
        raise ValueError("correlation_loss requires can_profile correlation for target roles")
    indices = [index for index, record in enumerate(output)
               if names.intersection(record["decoded_signals"])]
    selected = _phase_indices(indices, start, end)
    working = [{"decoded_signals": {
        name: value for name, value in output[index]["decoded_signals"].items()
        if name in names
    }} for index in selected]
    apply_correlation_failure(
        working, 0, len(working), "correlation_loss", matrix,
        onset_frames=max(1, len(working) // 3),
        decay_frames=max(1, len(working) // 3), envelope_mode="sigmoid",
        noise_multiplier=max(severity * parameters.get("magnitude", 0.2), 0.01),
        rng=np.random.default_rng(int(event_id[:16], 16) ^ seed),
    )
    result = []
    for ordinal, index in enumerate(selected):
        for role in roles:
            name = role_map[role].signal_name
            if name in working[ordinal]["decoded_signals"]:
                result.append(CorrelationCandidate(
                    index, role, float(working[ordinal]["decoded_signals"][name]),
                ))
    return tuple(result)


def _phase_indices(indices: list[int], start: float, end: float) -> list[int]:
    first = int(len(indices) * start)
    last = max(first + 1, int(len(indices) * end))
    return indices[first:min(last, len(indices))]


__all__ = ["CorrelationCandidate", "correlation_candidates"]

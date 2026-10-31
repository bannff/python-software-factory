"""Failure-mode injection for synthetic CAN data (Phases 3, 4, 5).

Supports four injection strategies:

* ``"rule"``        — the original eight fault modes
  (``signal_drift``, ``drop_to_zero``, ``out_of_sequence``,
  ``sensor_degradation``, ``ecu_timeout``, ``signal_freeze``,
  ``spike_noise``, ``correlation_break``).
* ``"learned"``     — every failure is sampled from a
  :data:`LearnedSampler` (typically a conditional TimeGAN trained on
  SCANIA APS patterns) and blended into the pre-failure context.
* ``"hybrid"``      — 30% rule / 70% learned, picked per event.
* ``"correlation"`` — uses a precomputed signal correlation matrix
  (typically emitted by ``can_profile``) to corrupt MULTIPLE
  correlated signals together with a gradual onset/sustained/decay
  envelope. Physically realistic: a single bus fault (EMI, connector
  corrosion) couples signals together, so a noisy root line
  propagates into its coupled neighbors.

Blending for the learned path is handled in
:mod:`_hybrid_injection_helpers`; the rule-mode primitives live in
:mod:`_rule_failure_helpers`; the correlation matrix math lives in
:mod:`_correlation_matrix_helpers` and the correlation orchestrator
in :mod:`_correlation_injection_helpers`. This file dispatches them
all and stays under the 200-LOC factory ceiling.

In-place mutation keeps the synthetic stream ordered so downstream
sequence-aware models see the same windowed anomalies they would on
a real bus.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import numpy as np

from ._correlation_injection_helpers import (
    DEFAULT_NOISE_MULTIPLIER,
    apply_correlation_failure,
    validate_correlation_strategy,
)
from ._hybrid_injection_helpers import (
    LEARNED_FAILURE_MODES,
    LearnedSampler,
    apply_learned_failure,
    pick_event_strategy,
    pick_learned_mode,
    validate_strategy,
)
from ._physical_failure_modes import PHYSICAL_RULE_DISPATCH
from ._post_injection_verification import verify_failure_rate
from ._rule_failure_helpers import _ALL_MODES, _DEFAULT_MODES, _RULE_DISPATCH

# Mode label recorded on each record for downstream observability.
CORRELATION_FAILURE_MODE: str = "correlation_failure"

# Onset/decay defaults: 3-frame onset/decay keeps the envelope visible on small windows.
DEFAULT_ONSET_FRAMES: int = 10
DEFAULT_DECAY_FRAMES: int = 10

_AVG_WINDOW = 4  # expected average window size for failure events

__all__ = [
    "inject_failures",
    "LEARNED_FAILURE_MODES",
    "LearnedSampler",
    "CORRELATION_FAILURE_MODE",
    "DEFAULT_ONSET_FRAMES",
    "DEFAULT_DECAY_FRAMES",
    "DEFAULT_NOISE_MULTIPLIER",
]


def inject_failures(
    records: list[dict[str, Any]],
    failure_rate: float,
    rng: np.random.Generator,
    failure_modes: tuple[str, ...] | None = None,
    *,
    injection_strategy: str = "rule",
    learned_sampler: LearnedSampler | None = None,
    correlation_matrix: Any = None,
    onset_frames: int = DEFAULT_ONSET_FRAMES,
    decay_frames: int = DEFAULT_DECAY_FRAMES,
    envelope_mode: str = "linear",
    noise_multiplier: float = DEFAULT_NOISE_MULTIPLIER,
) -> Iterator[dict[str, Any]]:
    """Mutate ``records`` to carry ~``failure_rate`` failures and yield them.

    ``failure_rate`` is the target fraction of records marked as
    failures. Since each event marks a 3-5 record window, the number of
    events is ``failure_rate * len(records) / avg_window`` so the
    realized fraction stays close to the configured rate.

    ``injection_strategy`` selects the failure source. ``"rule"`` is
    the legacy behavior; ``"learned"`` requires a ``learned_sampler``;
    ``"hybrid"`` mixes rule and learned per event (30/70 by default);
    ``"correlation"`` requires a ``correlation_matrix`` (typically
    from ``can_profile``) and produces physically-realistic failures
    on coupled signals with a gradual onset/decay envelope.
    """
    modes = failure_modes or _DEFAULT_MODES
    validate_strategy(injection_strategy, learned_sampler)
    validate_correlation_strategy(injection_strategy, correlation_matrix)
    if failure_rate <= 0.0 or not records or not modes:
        yield from records
        return

    target_marked = int(round(len(records) * failure_rate))
    n_events = max(1, target_marked // _AVG_WINDOW)
    if target_marked > 0 and n_events == 0:
        n_events = 1  # small streams still get at least one anomaly

    # Decide per-event strategy ahead of time so the realized mix is
    # deterministic given the seed (matches the contract of every other
    # stage in the can_synthesize pipeline).
    use_rule = _resolve_event_plan(injection_strategy, n_events, rng)

    picks: list[tuple[int, str, str]] = []
    cursor = 0
    rule_idx = learned_idx = 0
    while cursor < len(records) and len(picks) < n_events:
        event_strategy = use_rule[len(picks)]
        if event_strategy == "rule":
            mode = modes[rule_idx % len(modes)]
            rule_idx += 1
        elif event_strategy == "learned":
            mode = pick_learned_mode(learned_idx, rng)
            learned_idx += 1
        else:  # correlation
            mode = CORRELATION_FAILURE_MODE
        picks.append((cursor, mode, event_strategy))
        cursor += int(rng.integers(3, 6))

    for start, mode, event_strategy in picks:
        end = min(start + int(rng.integers(3, 6)), len(records))
        if event_strategy == "rule":
            _apply_rule_mode(records, start, end, mode, rng)
        elif event_strategy == "learned":
            apply_learned_failure(records, start, end, mode, learned_sampler, rng)
        else:  # correlation
            apply_correlation_failure(
                records, start, end, mode, correlation_matrix,
                onset_frames=onset_frames, decay_frames=decay_frames,
                envelope_mode=envelope_mode, noise_multiplier=noise_multiplier,
                rng=rng,
            )
        for i in range(start, end):
            r = records[i]
            r["is_failure"] = 1
            r["failure_mode"] = mode
            r["failure_timestamp_ns"] = r["timestamp_ns"]
            # The current event's strategy always wins, even if the
            # record was already tagged by a previous overlapping
            # event. This keeps ``failure_strategy`` consistent with
            # ``failure_mode`` for downstream observability.
            r["failure_strategy"] = event_strategy

    verify_failure_rate(records, failure_rate)
    yield from records


def _resolve_event_plan(
    injection_strategy: str, n_events: int, rng: np.random.Generator,
) -> list[str]:
    """Build the per-event strategy list for the configured mode."""
    if injection_strategy == "rule":
        return ["rule"] * n_events
    if injection_strategy == "learned":
        return ["learned"] * n_events
    if injection_strategy == "correlation":
        return ["correlation"] * n_events
    # Hybrid: 30% rule / 70% learned, drawn uniformly.
    return [pick_event_strategy(rng) for _ in range(n_events)]


def _apply_rule_mode(
    records: list[dict[str, Any]],
    start: int,
    end: int,
    mode: str,
    rng: np.random.Generator,
) -> None:
    """Dispatch a rule-based failure mode; unknown modes are a no-op."""
    dispatch = _RULE_DISPATCH if mode in {"ecu_timeout", "signal_freeze"} else PHYSICAL_RULE_DISPATCH
    handler = dispatch.get(mode)
    if handler is None:
        return
    handler(records, start, end, rng) if _needs_rng(handler) else handler(records, start, end)


def _needs_rng(handler: Any) -> bool:
    """The drop_to_zero / out_of_sequence / ecu_timeout handlers take 3 args."""
    return handler.__code__.co_argcount >= 4

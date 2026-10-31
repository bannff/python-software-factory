"""Per-CAN-ID synthesis dispatch for ``can_synthesize``.

Extracted from :mod:`can_synthesize` to keep that adapter under the
200-LOC factory ceiling. This module owns the per-CAN-ID
synthesis loop: SDV fit/sample → constraint clamp → failure
injection. It is invoked once per arbitration_id by the
:func:`can_synthesize._dispatch_synthesize` helper.
"""

from __future__ import annotations

from collections.abc import Iterator
import hashlib
from typing import Any

import numpy as np
import pandas as pd

from .can_synthesize_helpers import (
    build_records,
    clamp_to_constraints,
    fit_and_sample,
)
from .failure_injection import (
    DEFAULT_DECAY_FRAMES,
    DEFAULT_ONSET_FRAMES,
    inject_failures,
)


def dispatch_per_can_id(
    *,
    arb_id: str,
    group: list[dict[str, Any]],
    constraints: dict[str, Any],
    params: dict[str, Any],
    rng: np.random.Generator,
    learned_sampler: Any,
    correlation_matrix: Any,
) -> Iterator[dict[str, Any]]:
    """Synthesize ``multiplier * len(group)`` records for one CAN ID.

    ``params`` is the flat dict produced by
    :func:`can_synthesize._parse_config_params` — it carries every
    runtime setting so this helper can stay stateless.
    """
    signal_names = sorted({
        n for r in group for n in (r.get("decoded_signals") or {})
    })
    if not signal_names:
        return

    signal_meta = constraints.get("signals") or {}
    frame_rate = float(constraints.get("frame_rate_hz") or 0.0) or 1.0
    period_ns = max(int(1e9 / frame_rate), 1)
    template = group[0]
    n_synth = len(group) * params["multiplier"]

    df = pd.DataFrame(
        [[float((r.get("decoded_signals") or {}).get(n, 0.0)) for n in signal_names]
         for r in group],
        columns=signal_names,
    ).fillna(0.0)

    # Seed per CAN ID so the SDV draws differ across arbitration IDs
    # even with a single global seed.
    arb_seed = int.from_bytes(hashlib.sha256(arb_id.encode()).digest()[:4], "big")
    sdv_seed = int((params["seed"] + arb_seed) % (2**31))
    sampled = fit_and_sample(df, n_synth, sdv_seed=sdv_seed, method=params["method"])
    sampled = clamp_to_constraints(sampled, signal_meta, signal_names)

    synth = build_records(
        template=template, donors=group, arb_id=arb_id, signal_names=signal_names,
        values=sampled, period_ns=period_ns, vehicle_id=params["vehicle_id"],
    )
    yield from inject_failures(
        synth, params["failure_rate"], rng, params["failure_modes"] or None,
        injection_strategy=params["injection_strategy"],
        learned_sampler=learned_sampler,
        correlation_matrix=correlation_matrix,
        onset_frames=params.get("onset_frames", DEFAULT_ONSET_FRAMES),
        decay_frames=params.get("decay_frames", DEFAULT_DECAY_FRAMES),
    )

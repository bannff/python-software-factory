"""Built-in failure patterns declared as closed, provenance-bearing data."""
from __future__ import annotations

import hashlib

from .failure_pattern_codec import build_failure_pattern
from .failure_pattern_models import FailurePatternDraft, FailurePatternSpec

_SOURCE_VERSION = "08ee9b7f42ac98802990eceda37b883a44e159a6"
_SOURCE_URL = (
    "https://raw.githubusercontent.com/bannff/python-factory/"
    f"{_SOURCE_VERSION}/.github/spec/Rando.md"
)
_SOURCE_CONTENT = {
    "dbc-semantics": (
        "- Static boundary analysis (min/max/variance/clipping per signal)\n"
        "- Delta threshold computation (max rate-of-change per signal per timestep)\n"
        "- Output: JSON constraint schema consumed by downstream generators"
    ),
    "temporal-response": (
        "- Temporal windowing (rolling 5-second lookbacks, configurable overlap)\n"
        "- Failure label injection (anomalous patterns at synthetic failure timestamps)\n"
        "- Each synthetic record has ground-truth labels"
    ),
    "coupled-signals": (
        "- Temporal correlation detection (signal pairs that move together)\n"
        "- Correlation matrix showing signal relationships\n"
        "- Temporal correlations preserved in synthetic data"
    ),
}


def _source(source_id: str) -> dict:
    content = _SOURCE_CONTENT[source_id]
    return {
        "source_id": source_id, "source_url": _SOURCE_URL,
        "spdx_license": "BUSL-1.1", "version": _SOURCE_VERSION,
        "retrieved_at": "2026-08-03T04:34:50Z", "retrieved_content": content,
        "source_digest": hashlib.sha256(content.encode()).hexdigest(),
    }


def _evidence(source_id: str, locator: str) -> dict:
    return {
        "evidence_id": f"{source_id}-evidence", "source_id": source_id,
        "locator": locator, "range_start": 0,
        "range_end": len(_SOURCE_CONTENT[source_id]),
    }


_CONSTRAINTS = (
    {"kind": "minimum_roles", "value": 2},
    {"kind": "within_bounds", "value": 1},
    {"kind": "mutation_required", "value": 1},
)
_RAW = (
    {
        "pattern_id": "coupled-drift", "version": "1.0.0",
        "title": "Coupled thermal and rotational drift",
        "source_id": "dbc-semantics",
        "roles": ({"role": "thermal_state"}, {"role": "rotational_speed"}),
        "applicability": ({"role": "thermal_state", "operator": "present"},
                          {"role": "rotational_speed", "operator": "present"}),
        "phases": ({"phase_id": "drift", "start_fraction": 0.2,
                    "end_fraction": 0.8, "severity": 0.35,
                    "transforms": ({"kind": "additive_drift",
                                    "target_roles": ("thermal_state", "rotational_speed"),
                                    "parameters": {"magnitude": 0.25}},)},),
    },
    {
        "pattern_id": "response-lag", "version": "1.0.0",
        "title": "Command and response lag", "source_id": "temporal-response",
        "roles": ({"role": "command"}, {"role": "response"}),
        "applicability": ({"role": "command", "operator": "present"},
                          {"role": "response", "operator": "present"}),
        "phases": ({"phase_id": "lag", "start_fraction": 0.2,
                    "end_fraction": 0.9, "severity": 0.6,
                    "transforms": ({"kind": "response_lag",
                                    "target_roles": ("command", "response"),
                                    "parameters": {"lag_frames": 2}},)},),
    },
    {
        "pattern_id": "correlation-loss", "version": "1.0.0",
        "title": "Engine speed and thermal-state correlation loss",
        "source_id": "coupled-signals",
        "roles": ({"role": "rotational_speed"}, {"role": "thermal_state"}),
        "applicability": ({"role": "rotational_speed", "operator": "present"},
                          {"role": "thermal_state", "operator": "present"}),
        "phases": ({"phase_id": "decorrelate", "start_fraction": 0.15,
                    "end_fraction": 0.85, "severity": 0.45,
                    "transforms": ({"kind": "correlation_loss",
                                    "target_roles": ("rotational_speed", "thermal_state"),
                                    "parameters": {"magnitude": 0.3}},)},),
    },
)


def builtin_failure_patterns() -> tuple[FailurePatternSpec, ...]:
    patterns = []
    for item in _RAW:
        source_id = item["source_id"]
        body = {key: value for key, value in item.items() if key != "source_id"}
        patterns.append(build_failure_pattern(FailurePatternDraft.model_validate({
            **body, "sources": (_source(source_id),),
            "evidence": (_evidence(source_id, item["title"]),),
            "constraints": _CONSTRAINTS,
            "event_label_policy": {"positive_when": "actual_mutation"},
        })))
    return tuple(patterns)


__all__ = ["builtin_failure_patterns"]

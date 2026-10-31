"""Closed compiler for profile-bound, ScenarioPack-backed failure patterns."""
from __future__ import annotations

import hashlib
from typing import Any

from .adapters._correlation_matrix_helpers import build_envelope
from .dbc_semantics import DbcVersionDefinition
from .failure_pattern_constraints import compile_pattern_constraints, constrain_value
from .failure_pattern_correlation import correlation_candidates
from .failure_pattern_models import (
    FailurePatternBinding, FailurePatternLineage, FailurePatternSpec,
)
from .scenario_codec import canonical_json
from .scenario_lineage_models import ScenarioPackRef


def apply_failure_pattern(
    records: list[dict[str, Any]], pattern: FailurePatternSpec,
    binding: FailurePatternBinding, definition: DbcVersionDefinition, seed: int,
    *, constraint_schema: dict[str, Any], scenario_pack: ScenarioPackRef,
) -> tuple[list[dict[str, Any]], FailurePatternLineage]:
    """Compile and apply ordered phases; positive labels require real mutation."""
    if not records:
        raise ValueError("failure pattern cannot apply to an empty trajectory")
    output = [{**record, "decoded_signals": dict(record.get("decoded_signals") or {})}
              for record in records]
    for record in output:
        record.setdefault("is_failure", 0)
        record.setdefault("failure_mode", None)
    context = compile_pattern_constraints(
        pattern, binding, definition, output, constraint_schema,
    )
    input_digest = _records_digest(records)
    role_map = {item.role: item for item in binding.bindings}
    changed_roles: set[str] = set()
    event_ids: list[str] = []
    for phase in pattern.phases:
        event_id = hashlib.sha256(canonical_json({
            "seed": seed, "input": input_digest, "pattern": pattern.digest,
            "binding": binding.binding_digest, "scenario": scenario_pack.digest,
            "constraints": context.constraint_digest, "phase": phase.phase_id,
        })).hexdigest()
        event_ids.append(event_id)
        for transform in phase.transforms:
            if transform.kind == "correlation_loss":
                candidates = correlation_candidates(
                    output, transform.target_roles, role_map, context.correlations,
                    phase.start_fraction, phase.end_fraction, phase.severity,
                    transform.parameters, event_id, seed,
                )
                for candidate in candidates:
                    bound = role_map[candidate.role]
                    original = float(
                        output[candidate.record_index]["decoded_signals"][bound.signal_name]
                    )
                    changed = constrain_value(
                        original, candidate.value, context.by_role[candidate.role],
                    )
                    if changed == original:
                        continue
                    output[candidate.record_index]["decoded_signals"][bound.signal_name] = changed
                    changed_roles.add(candidate.role)
                    _label(
                        output[candidate.record_index], pattern, binding, definition,
                        scenario_pack, context.constraint_digest, event_id,
                        phase.phase_id, phase.severity, candidate.role,
                        bound.signal_name, seed,
                    )
                continue
            for role in transform.target_roles:
                bound = role_map[role]
                indices = [index for index, record in enumerate(output)
                           if bound.signal_name in record["decoded_signals"]]
                selected = _phase_indices(indices, phase.start_fraction, phase.end_fraction)
                envelope = build_envelope(
                    len(selected), max(1, len(selected) // 3),
                    max(1, len(selected) // 3), "sigmoid",
                )
                for ordinal, index in enumerate(selected):
                    original = float(output[index]["decoded_signals"][bound.signal_name])
                    candidate = _transform(
                        transform.kind, original, ordinal, selected, output,
                        bound.signal_name, phase.severity,
                        transform.parameters, float(envelope[ordinal]),
                    )
                    changed = constrain_value(original, candidate, context.by_role[role])
                    if changed == original:
                        continue
                    output[index]["decoded_signals"][bound.signal_name] = changed
                    changed_roles.add(role)
                    _label(output[index], pattern, binding, definition, scenario_pack,
                           context.constraint_digest, event_id, phase.phase_id,
                           phase.severity, role, bound.signal_name, seed)
    required = max((int(item.value) for item in pattern.constraints
                    if item.kind == "minimum_roles"), default=2)
    if len(changed_roles) < required:
        raise ValueError(
            f"failure pattern mutation constraint failed: changed {len(changed_roles)} "
            f"roles, required {required}"
        )
    _verify_constraints(output, pattern, role_map)
    lineage = FailurePatternLineage(
        deterministic_seed=seed, dbc_version=definition.version,
        dbc_digest=definition.digest, pattern=binding.pattern,
        scenario_pack=scenario_pack, binding_digest=binding.binding_digest,
        constraint_digest=context.constraint_digest,
        applicability_digest=context.applicability_digest,
        event_ids=tuple(event_ids), input_digest=input_digest,
        output_digest=_records_digest(output),
    )
    return output, lineage


def _phase_indices(indices: list[int], start: float, end: float) -> list[int]:
    first = int(len(indices) * start)
    last = max(first + 1, int(len(indices) * end))
    return indices[first:min(last, len(indices))]


def _transform(kind: str, value: float, ordinal: int, indices: list[int],
               records: list[dict[str, Any]], name: str, severity: float,
               params: dict[str, float], intensity: float) -> float:
    magnitude = severity * params.get("magnitude", 0.2) * intensity
    span = max(abs(value), 1.0)
    if kind == "additive_drift":
        return value + span * magnitude
    if kind == "response_lag":
        lag = max(1, int(params.get("lag_frames", 1)))
        source = max(0, ordinal - lag)
        delayed = float(records[indices[source]]["decoded_signals"].get(name, value))
        return value + intensity * (delayed - value)
    raise ValueError(f"unknown closed failure transform: {kind}")


def _label(record, pattern, binding, definition, scenario_pack, constraint_digest,
           event_id, phase, severity, role, signal_name, seed) -> None:
    record["is_failure"] = pattern.event_label_policy.positive_label
    record["failure_mode"] = pattern.pattern_id
    record["failure_strategy"] = "failure_pattern"
    prior = record.get("failure_event", {})
    record["failure_event"] = {
        "event_id": event_id, "phase": phase, "severity": severity,
        "changed_roles": sorted(set(prior.get("changed_roles", ())) | {role}),
        "changed_signals": sorted(set(prior.get("changed_signals", ())) | {signal_name}),
        "label_derivation": "actual_mutation", "deterministic_seed": seed,
        "dbc_version": definition.version, "dbc_digest": definition.digest,
        "pattern_id": pattern.pattern_id, "pattern_version": pattern.version,
        "pattern_digest": pattern.digest, "binding_digest": binding.binding_digest,
        "scenario_pack_digest": scenario_pack.digest,
        "constraint_digest": constraint_digest,
    }


def _verify_constraints(output, pattern, role_map) -> None:
    if not any(record.get("is_failure") == 1 for record in output):
        raise ValueError("failure pattern produced no actual mutation")
    for item in pattern.constraints:
        if item.kind != "maximum_delta":
            continue
        for bound in role_map.values():
            values = [float(record["decoded_signals"][bound.signal_name]) for record in output
                      if bound.signal_name in record["decoded_signals"]]
            if any(abs(right - left) > item.value for left, right in zip(values, values[1:])):
                raise ValueError(f"failure pattern maximum_delta violated for {bound.role}")


def _records_digest(records: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_json(records)).hexdigest()


__all__ = ["apply_failure_pattern"]

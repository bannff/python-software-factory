"""Compile bound patterns against observed CAN profile constraints."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dbc_semantics import DbcSignalDefinition, DbcVersionDefinition
from .failure_pattern_models import FailurePatternBinding, FailurePatternSpec
from .scenario_codec import canonical_json
import hashlib


@dataclass(frozen=True)
class BoundSignalConstraint:
    definition: DbcSignalDefinition
    minimum: float | None
    maximum: float | None
    delta_max: float


@dataclass(frozen=True)
class PatternConstraintContext:
    by_role: dict[str, BoundSignalConstraint]
    correlations: tuple[tuple[str, str, float], ...]
    constraint_digest: str
    applicability_digest: str


def compile_pattern_constraints(
    pattern: FailurePatternSpec, binding: FailurePatternBinding,
    definition: DbcVersionDefinition, records: list[dict[str, Any]],
    profile: dict[str, Any],
) -> PatternConstraintContext:
    messages = {message.message_id: message for message in definition.messages}
    signals = {signal.signal_id: signal for message in definition.messages
               for signal in message.signals}
    bound: dict[str, BoundSignalConstraint] = {}
    serialized: dict[str, Any] = {}
    correlations: set[tuple[str, str, float]] = set()
    for item in binding.bindings:
        message = messages[item.message_id]
        signal = signals[item.signal_id]
        can_profile = _can_profile(profile, message.arbitration_id)
        signal_profile = (can_profile.get("signals") or {}).get(item.signal_name)
        if not isinstance(signal_profile, dict):
            raise ValueError(f"can_profile constraint missing for role {item.role}")
        minimum = _number(signal_profile.get("min"))
        maximum = _number(signal_profile.get("max"))
        delta_max = _number(signal_profile.get("delta_max"))
        if minimum is None or maximum is None or delta_max is None:
            raise ValueError(f"can_profile bounds/delta missing for role {item.role}")
        observed_correlations = _correlations(can_profile.get("correlations"))
        correlations.update(observed_correlations)
        bound[item.role] = BoundSignalConstraint(signal, minimum, maximum, delta_max)
        serialized[item.role] = {
            "signal_id": item.signal_id, "minimum": minimum,
            "maximum": maximum, "delta_max": delta_max,
            "correlations": observed_correlations,
        }
    _check_applicability(pattern, binding, records)
    constraint_digest = hashlib.sha256(canonical_json({
        "profile": serialized,
        "pattern_constraints": [item.model_dump(mode="json")
                                for item in pattern.constraints],
    })).hexdigest()
    applicability_digest = hashlib.sha256(canonical_json([
        item.model_dump(mode="json") for item in pattern.applicability
    ])).hexdigest()
    return PatternConstraintContext(
        bound, tuple(sorted(correlations)), constraint_digest, applicability_digest,
    )


def constrain_value(original: float, candidate: float,
                    constraint: BoundSignalConstraint) -> float:
    lower = constraint.definition.minimum
    upper = constraint.definition.maximum
    lower = constraint.minimum if lower is None else max(lower, constraint.minimum)
    upper = constraint.maximum if upper is None else min(upper, constraint.maximum)
    delta = max(constraint.delta_max, 0.0)
    candidate = min(max(candidate, original - delta), original + delta)
    if lower is not None:
        candidate = max(candidate, lower)
    if upper is not None:
        candidate = min(candidate, upper)
    return candidate


def _can_profile(profile: dict[str, Any], arbitration_id: int) -> dict[str, Any]:
    for key, value in (profile.get("can_ids") or {}).items():
        try:
            if int(str(key), 0) == arbitration_id:
                return value
        except ValueError:
            continue
    raise ValueError(f"can_profile has no constraints for arbitration ID {arbitration_id:#x}")


def _check_applicability(pattern, binding, records) -> None:
    role_map = {item.role: item for item in binding.bindings}
    for predicate in pattern.applicability:
        item = role_map[predicate.role]
        values = [record["decoded_signals"][item.signal_name] for record in records
                  if item.signal_name in (record.get("decoded_signals") or {})]
        if predicate.operator == "present" and not values:
            raise ValueError(f"failure pattern applicability missing role {predicate.role}")
        if predicate.operator == "unit_in":
            allowed = {value.strip().casefold() for value in predicate.value.split("|")}
            if item.unit.casefold() not in allowed:
                raise ValueError(f"failure pattern applicability unit mismatch: {predicate.role}")
        if predicate.operator == "state_equals" and predicate.value not in {
            str(value) for value in values
        }:
            raise ValueError(f"failure pattern applicability state mismatch: {predicate.role}")


def _correlations(value: Any) -> tuple[tuple[str, str, float], ...]:
    if not isinstance(value, list):
        raise ValueError("can_profile correlations must be a list")
    result: list[tuple[str, str, float]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            raise ValueError("can_profile correlation entry is invalid")
        left, right, coefficient = item
        if not isinstance(left, str) or not isinstance(right, str):
            raise ValueError("can_profile correlation signals must be strings")
        result.append((left, right, float(coefficient)))
    return tuple(result)


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


__all__ = [
    "BoundSignalConstraint", "PatternConstraintContext",
    "compile_pattern_constraints", "constrain_value",
]

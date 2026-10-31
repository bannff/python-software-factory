"""Deterministic semantic-role binder with complete diagnostics."""
from __future__ import annotations

from .dbc_semantics import DbcVersionDefinition, SemanticRoleBinding
from .failure_pattern_codec import binding_digest, pattern_ref
from .failure_pattern_models import (
    FailureBindingReport, FailurePatternBinding, FailurePatternSpec,
)


def bind_failure_pattern(
    pattern: FailurePatternSpec, definition: DbcVersionDefinition,
) -> FailureBindingReport:
    """Bind every required role, reporting all missing/ambiguous/incompatible roles."""
    signals = [
        (message, signal) for message in definition.messages for signal in message.signals
    ]
    missing: list[str] = []
    ambiguous: dict[str, tuple[str, ...]] = {}
    incompatible: dict[str, tuple[str, ...]] = {}
    bindings: list[SemanticRoleBinding] = []
    for requirement in sorted(pattern.roles, key=lambda item: item.role):
        role_candidates = [(message, signal) for message, signal in signals
                           if requirement.role in signal.semantic_roles]
        compatible = [(message, signal) for message, signal in role_candidates
                      if not requirement.compatible_units
                      or signal.unit.casefold() in {unit.casefold() for unit in requirement.compatible_units}]
        if not role_candidates:
            missing.append(requirement.role)
            continue
        if not compatible:
            incompatible[requirement.role] = tuple(sorted(signal.signal_id for _, signal in role_candidates))
            continue
        if len(compatible) > 1:
            ambiguous[requirement.role] = tuple(sorted(signal.signal_id for _, signal in compatible))
            continue
        message, signal = compatible[0]
        bindings.append(SemanticRoleBinding(
            role=requirement.role, signal_id=signal.signal_id,
            message_id=message.message_id, signal_name=signal.name, unit=signal.unit,
        ))
    errors = tuple(
        [f"missing role: {role}" for role in missing]
        + [f"ambiguous role: {role}" for role in sorted(ambiguous)]
        + [f"incompatible role: {role}" for role in sorted(incompatible)]
    )
    if errors:
        return FailureBindingReport(
            status="invalid", missing_roles=tuple(missing), ambiguous_roles=ambiguous,
            incompatible_roles=incompatible, errors=errors,
        )
    serialized = [item.model_dump(mode="json") for item in sorted(bindings, key=lambda item: item.role)]
    digest_value = binding_digest({
        "pattern_digest": pattern.digest,
        "dbc_definition_id": definition.definition_id,
        "bindings": serialized,
    })
    binding = FailurePatternBinding(
        pattern=pattern_ref(pattern), dbc_definition_id=definition.definition_id,
        bindings=tuple(sorted(bindings, key=lambda item: item.role)),
        binding_digest=digest_value,
    )
    return FailureBindingReport(status="bound", binding=binding)


__all__ = ["bind_failure_pattern"]

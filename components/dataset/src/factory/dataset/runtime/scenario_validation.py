"""Cross-reference and coverage validation for ScenarioPack values."""
from __future__ import annotations

from collections.abc import Iterable

from .scenario_errors import ScenarioPackError
from .scenario_models import ScenarioPack, ScenarioPackDraft


def _ids(values: Iterable[object], field: str, label: str) -> set[str]:
    identifiers = [getattr(value, field) for value in values]
    if len(identifiers) != len(set(identifiers)):
        raise ScenarioPackError(f"Duplicate {label} IDs are not allowed")
    return set(identifiers)


def _require_refs(actual: Iterable[str], known: set[str], label: str) -> None:
    refs = list(actual)
    if len(refs) != len(set(refs)):
        raise ScenarioPackError(f"Duplicate {label} references are not allowed")
    dangling = sorted(set(refs) - known)
    if dangling:
        raise ScenarioPackError(f"Dangling {label} references: {dangling}")


def validate_scenario_pack(pack: ScenarioPackDraft | ScenarioPack) -> None:
    """Reject packs without complete source/evidence/scenario closure."""
    source_ids = _ids(pack.sources, "source_id", "source")
    evidence_ids = _ids(pack.evidence, "evidence_id", "evidence")
    claim_ids = _ids(pack.claims, "claim_id", "claim")
    assumption_ids = _ids(pack.assumptions, "assumption_id", "assumption")
    outcome_ids = _ids(pack.outcomes, "outcome_id", "outcome")
    _ids(pack.scenarios, "scenario_id", "scenario")

    used_sources: set[str] = set()
    for evidence in pack.evidence:
        _require_refs([evidence.source_id], source_ids, "evidence source")
        used_sources.add(evidence.source_id)
    used_evidence: set[str] = set()
    for claim in pack.claims:
        _require_refs(claim.evidence_ids, evidence_ids, "claim evidence")
        used_evidence.update(claim.evidence_ids)

    used_claims: set[str] = set()
    used_assumptions: set[str] = set()
    used_outcomes: set[str] = set()
    for scenario in pack.scenarios:
        _require_refs(scenario.claim_ids, claim_ids, "scenario claim")
        _require_refs(scenario.assumption_ids, assumption_ids, "scenario assumption")
        _require_refs(scenario.outcome_ids, outcome_ids, "scenario outcome")
        if not any(step.role == "user" for step in scenario.steps):
            raise ScenarioPackError(
                f"Scenario {scenario.scenario_id} must contain a user step"
            )
        used_claims.update(scenario.claim_ids)
        used_assumptions.update(scenario.assumption_ids)
        used_outcomes.update(scenario.outcome_ids)

    missing = {
        name: sorted(values) for name, values in {
            "sources": source_ids - used_sources,
            "evidence": evidence_ids - used_evidence,
            "claims": claim_ids - used_claims,
            "assumptions": assumption_ids - used_assumptions,
            "outcomes": outcome_ids - used_outcomes,
        }.items() if values
    }
    if missing:
        raise ScenarioPackError(f"ScenarioPack coverage is incomplete: {missing}")

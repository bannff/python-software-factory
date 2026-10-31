"""Bind approved patterns to DBC/profile constraints and ScenarioPack lineage."""
from __future__ import annotations

from typing import Any

from ..dbc_semantics import DbcVersionDefinition
from ..failure_pattern_apply import apply_failure_pattern
from ..failure_pattern_binding import bind_failure_pattern
from ..failure_pattern_models import FailurePatternRef
from ..failure_pattern_scenario import verify_failure_scenario
from ..scenario_lineage_models import ScenarioPackRef
from .failure_pattern_store import LocalFailurePatternStore


def apply_configured_patterns(
    records: list[dict[str, Any]], refs: list[dict[str, Any]],
    raw_definition: dict[str, Any], seed: int, constraint_schema: dict[str, Any],
    raw_scenarios: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve, bind, compile, and apply every immutable pattern artifact."""
    if not refs:
        return records
    if not raw_definition:
        raise ValueError("failure_pattern_refs require a canonical dbc_definition")
    definition = DbcVersionDefinition.model_validate(raw_definition)
    scenarios = [ScenarioPackRef.model_validate(item) for item in raw_scenarios]
    if len(scenarios) != len(refs):
        raise ValueError("failure patterns require one ScenarioPack artifact per reference")
    store = LocalFailurePatternStore()
    output = records
    lineage_items: list[dict[str, Any]] = []
    for raw_ref, scenario in zip(refs, scenarios, strict=True):
        ref = FailurePatternRef.model_validate(raw_ref)
        pattern = store.load(ref)
        if scenario.identity != f"can-failure-{pattern.pattern_id}" \
                or scenario.version != pattern.version:
            raise ValueError("failure pattern ScenarioPack applicability mismatch")
        verify_failure_scenario(scenario)
        report = bind_failure_pattern(pattern, definition)
        if report.status != "bound" or report.binding is None:
            details = "; ".join(report.errors) or "semantic role binding failed"
            raise ValueError(f"failure pattern {pattern.pattern_id} cannot bind: {details}")
        output, lineage = apply_failure_pattern(
            output, pattern, report.binding, definition, seed,
            constraint_schema=constraint_schema, scenario_pack=scenario,
        )
        lineage_items.append(lineage.model_dump(mode="json"))
    for record in output:
        record["scenario_kind"] = "generated_failure_scenario"
        record["failure_pattern_lineage"] = list(lineage_items)
    return output


__all__ = ["apply_configured_patterns"]

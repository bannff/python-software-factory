"""Concrete ScenarioPack and lineage DTOs for Dataset MCP egress."""
from __future__ import annotations

from typing import Literal

from pydantic import StrictInt, StrictStr

from .base import OutputDTO


class ScenarioPackRefOutput(OutputDTO):
    identity: StrictStr
    version: StrictStr
    uri: StrictStr
    digest: StrictStr


class ScenarioPackConflictOutput(OutputDTO):
    identity: StrictStr
    version: StrictStr
    existing_digest: StrictStr
    requested_digest: StrictStr
    reason: StrictStr


class ScenarioSourceOutput(OutputDTO):
    source_id: StrictStr
    uri: StrictStr
    digest: StrictStr
    license: StrictStr
    version: StrictStr


class ScenarioEvidenceOutput(OutputDTO):
    evidence_id: StrictStr
    source_id: StrictStr
    locator: StrictStr
    range_start: StrictInt
    range_end: StrictInt


class ScenarioClaimOutput(OutputDTO):
    claim_id: StrictStr
    statement: StrictStr
    evidence_ids: list[StrictStr]


class ScenarioAssumptionOutput(OutputDTO):
    assumption_id: StrictStr
    statement: StrictStr


class ScenarioOutcomeOutput(OutputDTO):
    outcome_id: StrictStr
    definition: StrictStr


class ScenarioStepOutput(OutputDTO):
    role: Literal["system", "user", "assistant"]
    content: StrictStr


class ScenarioDefinitionOutput(OutputDTO):
    scenario_id: StrictStr
    title: StrictStr
    setup: StrictStr
    steps: list[ScenarioStepOutput]
    claim_ids: list[StrictStr]
    assumption_ids: list[StrictStr]
    outcome_ids: list[StrictStr]


class ScenarioGenerationRuleOutput(OutputDTO):
    adapter: StrictStr
    version: StrictStr
    episodes_per_outcome: StrictInt


class ScenarioPackOutput(OutputDTO):
    status: Literal["published", "existing", "conflict"] | None = None
    ref: ScenarioPackRefOutput | None = None
    conflict: ScenarioPackConflictOutput | None = None
    identity: StrictStr | None = None
    version: StrictStr | None = None
    sources: list[ScenarioSourceOutput] | None = None
    evidence: list[ScenarioEvidenceOutput] | None = None
    claims: list[ScenarioClaimOutput] | None = None
    assumptions: list[ScenarioAssumptionOutput] | None = None
    outcomes: list[ScenarioOutcomeOutput] | None = None
    scenarios: list[ScenarioDefinitionOutput] | None = None
    generation_rule: ScenarioGenerationRuleOutput | None = None
    digest: StrictStr | None = None


class ScenarioEpisodeOutput(OutputDTO):
    episode_id: StrictStr
    episode_digest: StrictStr
    scenario_id: StrictStr
    outcome_id: StrictStr
    ordinal: StrictInt
    derived_seed: StrictInt
    split_group: StrictStr
    claim_ids: list[StrictStr]
    assumption_ids: list[StrictStr]


class ScenarioLineageOutput(OutputDTO):
    scenario_pack: ScenarioPackRefOutput
    sources: list[ScenarioSourceOutput]
    assumptions: list[ScenarioAssumptionOutput]
    generator_adapter: StrictStr
    generator_version: StrictStr
    seed: StrictInt
    episodes: list[ScenarioEpisodeOutput]

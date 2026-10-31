"""Canonical metadata and fail-closed registry for the first blueprint slice."""
from __future__ import annotations

import hashlib

from .blueprint_codec import canonical_digest
from .blueprint_models import (
    BlueprintResolution, DatasetBlueprint, DatasetCapabilityRef,
    DatasetOutputSchemaRef, DatasetRecipeRef, DatasetSourceEvidenceRef,
    DatasetStageRef,
)

SCENARIO_RECIPE_URI = "recipe://local/scenario-generate@1"
SCENARIO_RECIPE_REF = DatasetRecipeRef(
    id="scenario-generate", version="1",
    digest=hashlib.sha256(SCENARIO_RECIPE_URI.encode()).hexdigest(),
)
SCENARIO_STAGE_REF = DatasetStageRef(
    id="scenario_generate", version="scenario-generate-1.0",
    digest=canonical_digest({"adapter": "scenario_generate", "version": "scenario-generate-1.0"}),
)
GENERIC_SCHEMA_REF = DatasetOutputSchemaRef(
    id="generic", version="1.0",
    digest=canonical_digest({"record_schema": "generic", "version": "1.0"}),
)
SCENARIO_EVIDENCE_DESCRIPTOR = (
    "ScenarioPack", "1", canonical_digest({"kind": "ScenarioPack", "version": "1"})
)
DETERMINISTIC_TEMPLATE_REF = DatasetCapabilityRef(
    id="deterministic-template", version="1.0",
    digest=canonical_digest({
        "adapter": "dataset.deterministic-template", "version": "1.0",
    }),
)


class FixtureReferenceRegistry:
    """Exact allowlist; unknown IDs, versions, digests, or order fail closed."""

    def validate(self, blueprint: DatasetBlueprint) -> BlueprintResolution:
        if blueprint.recipe != SCENARIO_RECIPE_REF:
            raise ValueError("Unknown DatasetBlueprint recipe reference")
        if blueprint.stages != (SCENARIO_STAGE_REF,):
            raise ValueError("DatasetBlueprint stage references or order are not registered")
        if blueprint.output_schema != GENERIC_SCHEMA_REF:
            raise ValueError("Unknown DatasetBlueprint output schema reference")
        if blueprint.capabilities != (DETERMINISTIC_TEMPLATE_REF,):
            raise ValueError("Unknown DatasetBlueprint capability reference")
        if len(blueprint.source_evidence) != 1:
            raise ValueError("Exactly one ScenarioPack evidence reference is required")
        evidence: DatasetSourceEvidenceRef = blueprint.source_evidence[0]
        if (evidence.id, evidence.version, evidence.digest) != SCENARIO_EVIDENCE_DESCRIPTOR:
            raise ValueError("Unknown DatasetBlueprint source evidence reference")
        return BlueprintResolution(
            recipe_uri=SCENARIO_RECIPE_URI,
            stage_names=(SCENARIO_STAGE_REF.id,),
            record_schema="generic",
            generator_adapter="dataset.deterministic-template",
            generator_version="1.0",
        )


SCENARIO_RECIPE_SPEC = (
    "scenario-generate-v1", [{"name": SCENARIO_STAGE_REF.id, "config": {}}],
)

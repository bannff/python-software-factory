"""Default Dataset stage adapter registry."""
from __future__ import annotations

from pathlib import Path

from .adapters.can_artifact_stages import CanPriorPolicyStageAdapter, CanSignalSchemaStageAdapter
from .adapters.can_augment import CanAugmentStageAdapter
from .adapters.can_ingest import CanIngestStageAdapter
from .adapters.can_profile import CanProfileStageAdapter
from .adapters.can_synthesize import CanSynthesizeStageAdapter
from .adapters.can_taxonomize import CanTaxonomizeStageAdapter
from .adapters.can_window import CanWindowStageAdapter
from .adapters.can_window_v2 import CanWindowV2StageAdapter
from .adapters.context_augment import ContextAugmentStageAdapter
from .adapters.context_correlate import ContextCorrelateStageAdapter
from .adapters.context_ingest import ContextIngestStageAdapter
from .adapters.csv_can_ingest import CsvCanIngestStageAdapter
from .adapters.scenario_generate import ScenarioGenerateStageAdapter
from .ports import DatasetStagePort
from .blueprint_catalog import SCENARIO_STAGE_REF


class LocalValidationStage:
    name = "local-validate"
    stage_version = "factory-local-1"

    def execute(self, records, config=None):
        return records


def default_stages(storage_root: Path) -> dict[str, DatasetStagePort]:
    """Build the retained deterministic adapter map."""
    return {
        "local-validate": LocalValidationStage(),  # type: ignore[dict-item]
        SCENARIO_STAGE_REF.id: ScenarioGenerateStageAdapter(storage_root),
        "context_ingest": ContextIngestStageAdapter(),
        "context_correlate": ContextCorrelateStageAdapter(),
        "context_augment": ContextAugmentStageAdapter(),
        "can_ingest": CanIngestStageAdapter(),
        "csv_can_ingest": CsvCanIngestStageAdapter(),
        "can_profile": CanProfileStageAdapter(),
        "can_prior_policy": CanPriorPolicyStageAdapter(),
        "can_signal_schema": CanSignalSchemaStageAdapter(),
        "can_synthesize": CanSynthesizeStageAdapter(),
        "can_window": CanWindowStageAdapter(),
        "can_window_v2": CanWindowV2StageAdapter(),
        "can_augment": CanAugmentStageAdapter(),
        "can_taxonomize": CanTaxonomizeStageAdapter(),
    }

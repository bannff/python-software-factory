"""Dedicated Dataset stage adapter for immutable ScenarioPack generation."""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from ..scenario_generation import (
    generate_episodes, validate_scenario_lineage_against_pack,
)
from ..scenario_models import ScenarioPackGenerationInput, ScenarioPackLineage
from .scenario_store import LocalScenarioPackStore


class ScenarioGenerateStageAdapter:
    """Load one typed pack ref and emit its complete deterministic episodes."""

    name = "scenario_generate"
    stage_version = "scenario-generate-1.0"

    def __init__(self, storage_root: Path) -> None:
        self._store = LocalScenarioPackStore(storage_root, create=False)
        self.scenario_lineage: ScenarioPackLineage | None = None

    def execute(
        self,
        records: Iterable[Any],
        config: Mapping[str, Any] | None = None,
    ) -> Iterator[Any]:
        self.scenario_lineage = None
        if list(records):
            raise ValueError("scenario_generate does not accept ordinary input records")
        generation = ScenarioPackGenerationInput.model_validate(
            dict(config or {}).get("scenario_generation")
        )
        pack = self._store.load(generation.scenario_pack)
        episodes, lineage = generate_episodes(pack, generation)
        self.scenario_lineage = lineage
        yield from episodes


    def validate_lineage(
        self, records: list[Any], lineage: ScenarioPackLineage | None,
    ) -> None:
        """Verify resumed lineage against the immutable canonical pack."""
        if lineage is None:
            raise ValueError("Scenario generation lineage is missing")
        pack = self._store.load(lineage.scenario_pack)
        validate_scenario_lineage_against_pack(records, lineage, pack)

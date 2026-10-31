"""Read-only MCP tools for immutable dataset artifacts."""
from __future__ import annotations

from pathlib import Path

from typing import Any

from factory.mcp_utils.interface import ToolResult, deterministic

from .contracts.lifecycle import (
    ArtifactOutput, DatasetUriInput, JobInput, ScenarioPackInput,
)
from .contracts.resolved_artifact import ResolvedArtifactOutput
from .contracts.trajectory import ResolvedTrajectoryZoneOutput, TrajectoryZoneInput
from .contracts.scenario_outputs import ScenarioPackOutput
from ..interface import (
    dataset_get_artifact, dataset_get_scenario_pack, dataset_resolve_artifact,
    dataset_resolve_trajectory_zone,
)


def register(mcp: Any, storage_root: Path | None = None) -> None:
    """Register deterministic artifact resolution tools."""
    registered_root = storage_root

    @mcp.tool(name="dataset_get_scenario_pack")
    @deterministic(input_model=ScenarioPackInput, output_model=ScenarioPackOutput)
    def get_scenario_pack(
        identity: str, version: str, uri: str, digest: str,
        storage_root: str | None = None,
    ) -> ToolResult[ScenarioPackOutput]:
        """Load and verify a ScenarioPack through a flat typed reference."""
        from ..runtime.scenario_models import ScenarioPackRef
        root = Path(storage_root) if storage_root is not None else registered_root
        pack = dataset_get_scenario_pack(
            ScenarioPackRef(
                identity=identity, version=version, uri=uri, digest=digest,
            ),
            root,
        )
        return pack.model_dump(mode="json")

    @mcp.tool(name="dataset_get_artifact")
    @deterministic(input_model=JobInput, output_model=ArtifactOutput)
    def get_artifact(
        job_id: str, storage_root: str | None = None,
    ) -> ToolResult[ArtifactOutput]:
        """Return an artifact, optionally selecting a caller-owned store root."""
        root = Path(storage_root) if storage_root is not None else registered_root
        artifact = dataset_get_artifact(job_id, root)
        return artifact.model_dump(mode="json") if artifact else None

    @mcp.tool(name="dataset_resolve_artifact")
    @deterministic(input_model=DatasetUriInput, output_model=ResolvedArtifactOutput)
    def resolve_artifact(
        dataset_uri: str, storage_root: str | None = None,
    ) -> ToolResult[ResolvedArtifactOutput]:
        """Resolve a dataset URI within the caller-selected store root."""
        root = Path(storage_root) if storage_root is not None else registered_root
        manifest = dataset_resolve_artifact(dataset_uri, root)
        return manifest.model_dump(mode="json") if manifest else None

    @mcp.tool(name="dataset_resolve_trajectory_zone")
    @deterministic(input_model=TrajectoryZoneInput, output_model=ResolvedTrajectoryZoneOutput)
    def resolve_trajectory_zone(
        dataset_uri: str, storage_root: str | None = None,
    ) -> ToolResult[ResolvedTrajectoryZoneOutput]:
        """Resolve a digest-verified trajectory landing-zone rowset."""
        zone = dataset_resolve_trajectory_zone(dataset_uri, storage_root)
        return ResolvedTrajectoryZoneOutput.model_validate(zone).model_dump(mode="json")

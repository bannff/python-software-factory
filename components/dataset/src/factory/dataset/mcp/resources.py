"""MCP resources describing the stable dataset contract."""

from __future__ import annotations

import json
from pathlib import Path

from typing import Any

from ..runtime.contracts import (
    DatasetArtifactRef,
    DatasetGenerationRequest,
    DatasetJobReceipt,
    DatasetJobStatus,
    DatasetManifest,
)
from ..runtime.scenario_models import ScenarioPack, ScenarioPackDraft, ScenarioPackLineage
from ..runtime.dbc_models import DbcCatalogEntry, DbcResolution
from ..runtime.dbc_semantics import DbcVersionDefinition, DecodedSignalObservation
from ..runtime.failure_pattern_models import FailurePatternLineage, FailurePatternSpec
from ..runtime.blueprint_models import DatasetBlueprint


def register(mcp: Any, storage_root: Path | None = None) -> None:
    """Register schema and capability resources for dataset consumers."""

    @mcp.resource("dataset://schemas/blueprint")
    def blueprint_schema() -> str:
        """Get the closed immutable DatasetBlueprint JSON schema."""
        return json.dumps(DatasetBlueprint.model_json_schema(), indent=2)

    @mcp.resource("dataset://schemas/generation-request")
    def generation_request_schema() -> str:
        """Get the generation request JSON schema."""
        return json.dumps(DatasetGenerationRequest.model_json_schema(), indent=2)

    @mcp.resource("dataset://schemas/job")
    def job_schema() -> str:
        """Get the job receipt and status JSON schemas."""
        return json.dumps(
            {"receipt": DatasetJobReceipt.model_json_schema(), "status": DatasetJobStatus.model_json_schema()},
            indent=2,
        )

    @mcp.resource("dataset://schemas/artifact")
    def artifact_schema() -> str:
        """Get the artifact and manifest JSON schemas."""
        return json.dumps(
            {"artifact": DatasetArtifactRef.model_json_schema(), "manifest": DatasetManifest.model_json_schema()},
            indent=2,
        )

    @mcp.resource("dataset://schemas/scenario-pack")
    def scenario_pack_schema() -> str:
        """Get ScenarioPack draft, immutable artifact, and lineage schemas."""
        return json.dumps({
            "draft": ScenarioPackDraft.model_json_schema(),
            "pack": ScenarioPack.model_json_schema(),
            "lineage": ScenarioPackLineage.model_json_schema(),
        }, indent=2)

    @mcp.resource("dataset://schemas/can-intelligence")
    def can_intelligence_schema() -> str:
        """Get canonical DBC, observation, resolution, pattern, and lineage schemas."""
        return json.dumps({
            "dbc_catalog_entry": DbcCatalogEntry.model_json_schema(),
            "dbc_resolution": DbcResolution.model_json_schema(),
            "dbc_definition": DbcVersionDefinition.model_json_schema(),
            "decoded_observation": DecodedSignalObservation.model_json_schema(),
            "failure_pattern": FailurePatternSpec.model_json_schema(),
            "failure_lineage": FailurePatternLineage.model_json_schema(),
        }, indent=2)

    @mcp.resource("dataset://dbc/catalog")
    def dbc_catalog() -> str:
        """Return approved DBC catalog metadata and local verification status."""
        from ..runtime.can_intelligence import query_dbc_catalog
        return json.dumps(query_dbc_catalog(storage_root or Path(".dataset_store")), indent=2)

    @mcp.resource("dataset://can/failure-patterns")
    def failure_patterns() -> str:
        """Return all immutable evidence-backed failure-pattern references."""
        from ..runtime.can_intelligence import list_failure_patterns
        return json.dumps({"patterns": list_failure_patterns()}, indent=2)

    @mcp.resource("dataset://can/failure-patterns/{pattern_id}")
    def failure_pattern(pattern_id: str) -> str:
        """Return one approved pattern with evidence and canonical digest."""
        from ..runtime.can_intelligence import inspect_failure_pattern
        return json.dumps(inspect_failure_pattern(pattern_id), indent=2)

    @mcp.resource("dataset://docs/can-intelligence-scope")
    def can_intelligence_scope() -> str:
        """Acceptance boundary for the first evidence-backed CAN vertical slice."""
        return json.dumps({
            "output_classification": "generated_failure_scenario",
            "implemented": [
                "offline approved DBC discovery", "canonical DBC semantics",
                "three evidence-backed multi-signal failure patterns",
                "event-derived labels", "MCP Graph projection",
            ],
            "deferred": [
                "promotion-quality reports, leakage analysis, and synthetic-real quality claims",
                "LNN and Chronos2 training, passports, restart, promotion, and inference",
                "model tamper, crash, timeout, and restart handling",
                "network connectors and catalog expansion",
                "real Toyota/Kia service or DTC oracle and physical prediction claims",
            ],
        }, indent=2)

    @mcp.resource("dataset://jobs/{job_id}/logs")
    def job_logs(job_id: str) -> str:
        """Return the captured worker log for a dataset job."""
        root = storage_root or Path(".dataset_store")
        log_path = root / "jobs" / f"{job_id}.log"
        if not log_path.exists():
            return ""
        return log_path.read_text(encoding="utf-8", errors="replace")

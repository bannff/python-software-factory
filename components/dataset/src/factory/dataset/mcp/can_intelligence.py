"""Deterministic MCP discovery surface for DBCs and failure patterns."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic
from pydantic import StrictInt

from .contracts.can import (
    DbcCandidateOutput, DbcCatalogInput, DbcCatalogOutput, EmptyInput, FailurePatternInput,
    FailurePatternListOutput, FailurePatternOutput, ResolveDbcCandidateInput,
)
from ..interface import (
    dataset_inspect_failure_pattern, dataset_list_failure_patterns,
    dataset_query_dbc_catalog, dataset_resolve_dbc_candidate,
)
from ..runtime.dbc_models import MessageFingerprint


def register(mcp: Any, storage_root: Path) -> None:
    @mcp.tool(name="dataset_query_dbc_catalog")
    @deterministic(input_model=DbcCatalogInput, output_model=DbcCatalogOutput)
    def query_dbc_catalog(
        storage_root_override: str | None = None,
    ) -> ToolResult[DbcCatalogOutput]:
        """List approved local DBC metadata and fail-closed artifact status."""
        root = Path(storage_root_override) if storage_root_override else storage_root
        return dataset_query_dbc_catalog(root)

    @mcp.tool(name="dataset_resolve_dbc_candidate")
    @deterministic(input_model=ResolveDbcCandidateInput, output_model=DbcCandidateOutput)
    def resolve_dbc_candidate(
        catalog_id: str = "", version: str = "", vehicle_alias: str = "",
        vehicle_make: str = "", vehicle_model: str = "",
        vehicle_year: StrictInt | None = None,
        message_fingerprints: list[MessageFingerprint] | None = None,
        threshold: int = 10, storage_root_override: str | None = None,
    ) -> ToolResult[DbcCandidateOutput]:
        """Rank or verify one candidate, returning explanations and ambiguity."""
        root = Path(storage_root_override) if storage_root_override else storage_root
        fingerprints = [
            MessageFingerprint.model_validate(item).model_dump(mode="json")
            for item in (message_fingerprints or [])
        ]
        return dataset_resolve_dbc_candidate(
            root, catalog_id=catalog_id, version=version,
            vehicle_alias=vehicle_alias, vehicle_make=vehicle_make,
            vehicle_model=vehicle_model, vehicle_year=vehicle_year,
            message_fingerprints=fingerprints, threshold=threshold,
        )

    @mcp.tool(name="dataset_list_failure_patterns")
    @deterministic(input_model=EmptyInput, output_model=FailurePatternListOutput)
    def list_failure_patterns() -> ToolResult[FailurePatternListOutput]:
        """List immutable approved failure-pattern references."""
        patterns = dataset_list_failure_patterns()
        return {"patterns": patterns, "count": len(patterns)}

    @mcp.tool(name="dataset_inspect_failure_pattern")
    @deterministic(input_model=FailurePatternInput, output_model=FailurePatternOutput)
    def inspect_failure_pattern(
        pattern_id: str, version: str = "",
    ) -> ToolResult[FailurePatternOutput]:
        """Inspect one approved pattern including roles, phases, evidence, and digest."""
        return dataset_inspect_failure_pattern(pattern_id, version)


__all__ = ["register"]

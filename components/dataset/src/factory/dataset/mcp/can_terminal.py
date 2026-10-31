"""Operational MCP surface for canonical CAN training-bundle materialization."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from factory.mcp_utils.interface import ToolResult, operational
from pydantic import StrictInt

from .contracts.can import CanTerminalInput, CanTerminalOutput
from ..interface import dataset_materialize_can_training_bundle
from ..runtime.can_terminal_models import CanTerminalRequest
from ..runtime.can_terminal_paths import select_storage_root
from ..runtime.dbc_models import MessageFingerprint


def register(mcp: Any, storage_root: Path | None = None) -> None:
    """Register the synchronous, attempt-bound Dataset terminal."""
    registered_root = storage_root

    @mcp.tool(name="dataset_materialize_can_training_bundle")
    @operational(input_model=CanTerminalInput, output_model=CanTerminalOutput)
    def materialize_can_training_bundle(
        attempt_id: str, mf4_dir: str, dbc_path: str | None = None,
        vehicle_id: str = "unknown", dbc_catalog_id: str = "",
        dbc_catalog_version: str = "", vehicle_alias: str = "",
        vehicle_make: str = "", vehicle_model: str = "",
        vehicle_year: StrictInt | None = None,
        message_fingerprints: list[MessageFingerprint] | None = None,
        failure_pattern_refs: list[dict[str, Any]] | None = None,
        storage_root: str | None = None, max_samples: int = 20_000,
        config_overrides: dict[str, dict[str, Any]] | None = None,
        use_context: bool = False, context_sources: list[str] | None = None,
        emit_timespans: bool = False,
    ) -> ToolResult[CanTerminalOutput]:
        """Synchronously materialize an immutable, ML-ready CAN causal bundle."""
        request = CanTerminalRequest(
            attempt_id=attempt_id, mf4_dir=mf4_dir, dbc_path=dbc_path,
            dbc_catalog_id=dbc_catalog_id, dbc_catalog_version=dbc_catalog_version,
            vehicle_alias=vehicle_alias, vehicle_make=vehicle_make, vehicle_model=vehicle_model,
            vehicle_year=vehicle_year, message_fingerprints=tuple(message_fingerprints or ()),
            failure_pattern_refs=tuple(failure_pattern_refs or ()), vehicle_id=vehicle_id,
            max_samples=max_samples, config_overrides=config_overrides or {}, use_context=use_context,
            context_sources=context_sources or (), emit_timespans=emit_timespans,
        )
        if registered_root is None:
            raise ValueError("Dataset terminal requires a configured storage root")
        return dataset_materialize_can_training_bundle(request, select_storage_root(registered_root, storage_root))


__all__ = ["register"]

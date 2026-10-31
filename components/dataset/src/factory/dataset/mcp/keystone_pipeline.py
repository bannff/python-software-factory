"""Dataset-side discoverability for canonical CAN materialization."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic

from .contracts.can import CanPipelineOverviewOutput, EmptyInput

_TERMINAL = {
    "tool_name": "dataset_materialize_can_training_bundle", "mcp_server": "dataset",
    "category": "operational", "owner": "dataset",
    "stages": [
        {"stage": "ingest", "recipe": "recipe://local/can-ingest@1"},
        {"stage": "profile", "recipe": "recipe://local/can-profile@1"},
        {"stage": "context", "optional": True},
        {"stage": "synthesize", "recipe": "recipe://local/can-synthesize@1"},
        {"stage": "window", "recipe": "recipe://local/can-window@2"},
        {"stage": "augment", "recipe": "recipe://local/can-augment@1"},
        {"stage": "prepare", "outputs": ["feature_contract", "X", "y", "timespans"]},
    ],
    "description": ("Synchronous, durable CAN materialization terminal. It binds an explicit "
                    "workflow attempt to exact source bytes and returns a verified immutable "
                    "training bundle without importing or running Machine Learning."),
    "required_parameters": ["attempt_id", "mf4_dir", "dbc_path"],
    "optional_parameters": {"vehicle_id": "unknown", "storage_root": ".dataset_store",
                            "max_samples": 20_000, "config_overrides": {}, "use_context": False,
                            "context_sources": [], "emit_timespans": False},
    "idempotency": {"equal_retry": "returns the exact prior terminal output",
                    "divergent_retry": "returns status=conflict before new effects"},
    "returns": {"status": "completed on success", "artifacts": "Role-keyed uri/sha256/evidence map",
                "training_bundle": "Immutable Dataset refs plus prepared X/y/contracts",
                "legacy_projection": "ingest/profile/contracts/synthesize/window/augment/context"},
}


def register(mcp: Any) -> None:
    """Register CAN terminal metadata on the Dataset MCP server."""

    @mcp.tool(name="can_pipeline_overview")
    @deterministic(input_model=EmptyInput, output_model=CanPipelineOverviewOutput)
    def can_pipeline_overview() -> ToolResult[CanPipelineOverviewOutput]:
        """Describe the Dataset-owned CAN materialization terminal."""
        return dict(_TERMINAL)


__all__ = ["register"]

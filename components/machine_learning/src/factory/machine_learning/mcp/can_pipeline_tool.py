"""Typed MCP surface for the keystone CAN pipeline tool."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import fail, ok, operational
from factory.mcp_utils.runtime.tool_result import ToolResult

from ..runtime.can_keystone import run_keystone_pipeline
from ..runtime.can_model_configs import CanModelConfigs
from ..runtime.runtime import TrackingRuntime
from .timeseries_pipeline_models import CanPipelineInput, CanPipelineOutput


def register(mcp: Any, get_runtime: Callable[[], TrackingRuntime]) -> None:
    """Register the keystone CAN pipeline tool on the MCP server."""

    @mcp.tool(name="can_run_full_pipeline")
    @operational(input_model=CanPipelineInput, output_model=CanPipelineOutput)
    def can_run_full_pipeline(
        mf4_dir: str, dbc_path: str, vehicle_id: str = "unknown",
        storage_root: str | None = None, max_samples: int = 20_000,
        top_n_can_ids: int = 5, config_overrides: dict[str, Any] | None = None,
        use_context: bool = False, context_sources: list[str] | None = None,
        model_types: list[str] | None = None, model_configs: CanModelConfigs | None = None,
    ) -> ToolResult[CanPipelineOutput]:
        """Run ingest → profile → [context] → synthesize → window → augment → train."""
        result = run_keystone_pipeline(
            mf4_dir=mf4_dir, dbc_path=dbc_path, vehicle_id=vehicle_id,
            storage_root=storage_root, max_samples=max_samples, top_n_can_ids=top_n_can_ids,
            config_overrides=config_overrides, use_context=use_context,
            context_sources=context_sources, model_types=model_types,
            model_configs=(
                CanModelConfigs.model_validate(model_configs).model_dump(
                    mode="json", exclude_none=True,
                ) if model_configs else None
            ),
            runtime=get_runtime(),
        )
        if error := result.get("error"):
            return fail(str(error))
        return ok(CanPipelineOutput.model_validate(result))


__all__ = ["register"]

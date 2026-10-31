"""Security-gated typed authoring MCP tools for machine_learning."""
from __future__ import annotations

from typing import Any, Callable
from factory.mcp_utils.interface import ToolResult, authoring as authoring_decorator, fail
from ..runtime.authoring_policy import authoring_enabled
from ..runtime.chronos_acquisition import acquire_chronos2_backbone
from ..runtime.runtime import TrackingRuntime
from .authoring_contracts import (
    ChronosAcquisitionOutput, ConfigureTrainingDefaultsInput, EmptyInput,
    RegisterBaseModelInput, RegisterBaseModelOutput, TrainingDefaultsOutput,
)

_training_defaults: dict[str, Any] = {}
_model_registry: dict[str, dict[str, Any]] = {}
_DISABLED = "Authoring tools disabled. Set ML_ENABLE_AUTHORING_TOOLS=1"


def _authoring_enabled() -> bool:
    """Compatibility policy accessor used by the passport tool family."""
    return authoring_enabled()


def register(mcp: Any, get_runtime: Callable[[], TrackingRuntime]) -> None:
    """Register typed, security-gated authoring tools."""
    @mcp.tool()
    @authoring_decorator(input_model=EmptyInput, output_model=ChronosAcquisitionOutput)
    def ml_acquire_chronos2_backbone() -> ToolResult[ChronosAcquisitionOutput]:
        receipt = acquire_chronos2_backbone(get_runtime().chronos_storage_root())
        return ChronosAcquisitionOutput(**receipt.model_dump(mode="json"))

    @mcp.tool()
    @authoring_decorator(input_model=ConfigureTrainingDefaultsInput, output_model=TrainingDefaultsOutput)
    def ml_configure_training_defaults(batch_size: int | None = None, learning_rate: float | None = None, max_seq_length: int | None = None, optimizer: str | None = None, lora_rank: int | None = None, lora_alpha: int | None = None) -> ToolResult[TrainingDefaultsOutput]:
        if not authoring_enabled():
            return fail(_DISABLED)
        updates = {key: value for key, value in {"batch_size": batch_size, "learning_rate": learning_rate, "max_seq_length": max_seq_length, "optimizer": optimizer, "lora_rank": lora_rank, "lora_alpha": lora_alpha}.items() if value is not None}
        _training_defaults.update(updates)
        return TrainingDefaultsOutput(ok=True, defaults=dict(_training_defaults))

    @mcp.tool()
    @authoring_decorator(input_model=RegisterBaseModelInput, output_model=RegisterBaseModelOutput)
    def ml_register_base_model(name: str, model_id: str, description: str = "", recommended_method: str = "lora") -> ToolResult[RegisterBaseModelOutput]:
        if not authoring_enabled():
            return fail(_DISABLED)
        entry = {"name": name, "model_id": model_id, "description": description, "recommended_method": recommended_method}
        _model_registry[name] = entry
        return RegisterBaseModelOutput(ok=True, model=entry, total_models=len(_model_registry))

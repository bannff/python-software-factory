"""Early typed per-family configuration preflight for the CAN pipeline."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from .adapters.chronos_identity import exact_lora_config
from .chronos_acquisition import validate_chronos_backbone_ref
from .can_training_config import resolve_model_types
from .ports import (
    TimeSeriesModelConfig, TimeSeriesModelType, validate_model_config_for_family,
)


class CanModelConfigs(BaseModel):
    """Closed public MCP object for optional per-classifier configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    lightgbm: TimeSeriesModelConfig | None = None
    lstm: TimeSeriesModelConfig | None = None
    tcn: TimeSeriesModelConfig | None = None
    patchtst: TimeSeriesModelConfig | None = None
    chronos: TimeSeriesModelConfig | None = None
    lnn: TimeSeriesModelConfig | None = None


def preflight_can_model_configs(
    model_types: list[TimeSeriesModelType] | list[str] | None,
    model_configs: dict[str, Any] | None,
    chronos_storage_root: str | None = None,
) -> tuple[list[TimeSeriesModelType], dict[TimeSeriesModelType, TimeSeriesModelConfig | None]]:
    """Validate selection and all family configs before Dataset/training work."""
    requested = resolve_model_types(model_types)
    raw = dict(model_configs or {})
    requested_names = {item.value for item in requested}
    extras = sorted(set(raw) - requested_names)
    if extras:
        raise ValueError(f"model_configs contains unrequested families: {extras}")
    parsed: dict[TimeSeriesModelType, TimeSeriesModelConfig | None] = {}
    for model_type in requested:
        value = raw.get(model_type.value)
        if value is None:
            config = None
        elif isinstance(value, TimeSeriesModelConfig):
            config = value
        elif isinstance(value, dict):
            config = TimeSeriesModelConfig.model_validate(value)
        else:
            raise ValueError(f"{model_type.value} model_config must be an object")
        validate_model_config_for_family(model_type, config)
        if model_type is TimeSeriesModelType.chronos:
            assert config is not None and config.local_backbone_ref is not None
            if config.lora:
                assert config.lora_config is not None
                exact_lora_config(config.lora_config.to_runtime())
            validate_chronos_backbone_ref(
                config.local_backbone_ref, chronos_storage_root,
            )
        parsed[model_type] = config
    return requested, parsed


__all__ = ["CanModelConfigs", "preflight_can_model_configs"]

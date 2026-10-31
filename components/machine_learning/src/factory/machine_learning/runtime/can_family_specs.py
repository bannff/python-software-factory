"""Declarative Dataset and training contracts for CAN model families."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ports import TimeSeriesModelConfig, TimeSeriesModelType


@dataclass(frozen=True)
class CanFamilySpec:
    model_type: TimeSeriesModelType
    x_ref: str
    required_refs: frozenset[str]
    timing_ref: str | None = None
    evaluation_required: bool = False

    def model_config(
        self, refs: dict[str, dict[str, Any]], value: dict[str, Any] | None,
    ) -> TimeSeriesModelConfig | None:
        supplied = TimeSeriesModelConfig.model_validate(value) if value else None
        if self.timing_ref is None:
            return supplied
        if supplied is not None and (
            supplied.auxiliary_uris or supplied.local_backbone_ref is not None
            or supplied.lora or supplied.lora_config is not None
        ):
            raise ValueError("LNN lifecycle model_config is derived from exact timing refs")
        return TimeSeriesModelConfig(
            auxiliary_uris={"timespans": refs[self.timing_ref]["uri"]},
        )


FAMILY_SPECS: dict[str, CanFamilySpec] = {
    "lightgbm": CanFamilySpec(
        TimeSeriesModelType.lightgbm, "x_2d",
        frozenset({"contract", "x_2d", "y"}), evaluation_required=True,
    ),
    "chronos": CanFamilySpec(
        TimeSeriesModelType.chronos, "x_3d",
        frozenset({"contract", "x_3d", "y"}),
    ),
    "lnn": CanFamilySpec(
        TimeSeriesModelType.lnn, "x_3d",
        frozenset({"contract", "x_3d", "y", "timespans"}), "timespans",
    ),
}


def family_spec(value: str) -> CanFamilySpec:
    try:
        return FAMILY_SPECS[value]
    except KeyError as exc:
        raise ValueError(f"unsupported CAN lifecycle model_family: {value}") from exc


__all__ = ["CanFamilySpec", "FAMILY_SPECS", "family_spec"]

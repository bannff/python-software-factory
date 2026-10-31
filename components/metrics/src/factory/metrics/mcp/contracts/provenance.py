"""Flat MCP DTOs for subject-focused Metrics measurement."""
from __future__ import annotations

from pydantic import ConfigDict, JsonValue

from .deterministic import _Strict
from ...runtime.provenance_models import (
    EntityFocus, EvalFocus, ExecutionFocus, LiveFocus, MetricFocus,
    MetricMeasurement, MetricResult, NavigationRef, RunFocus, SessionFocus,
    SystemFocus, TimeRange, TraceFocus,
)


class MeasureInput(_Strict):
    focus: dict[str, JsonValue]


class MeasureOutput(MetricMeasurement):
    model_config = ConfigDict(extra="forbid", strict=True)


__all__ = [
    "EntityFocus", "EvalFocus", "ExecutionFocus", "LiveFocus", "MetricFocus",
    "MeasureInput", "MeasureOutput", "MetricMeasurement", "MetricResult",
    "NavigationRef", "RunFocus", "SessionFocus", "SystemFocus", "TimeRange",
    "TraceFocus",
]

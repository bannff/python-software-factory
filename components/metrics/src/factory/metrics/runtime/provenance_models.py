"""Strict subject-focused Metrics provenance contracts."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator


class MetricsProvenanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TimeRange(MetricsProvenanceModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def ordered(self) -> "TimeRange":
        if self.end <= self.start:
            raise ValueError("time_range.end must be after time_range.start")
        return self


class BoundedGraphContext(MetricsProvenanceModel):
    query_ref: str = Field(min_length=1, max_length=256)
    neighborhood_limit: PositiveInt = Field(le=200)


class NavigationRef(MetricsProvenanceModel):
    version: Literal["v1"] = "v1"
    surface: Literal["graph", "timeline", "evals", "owner", "metrics"]
    target_ref: str = Field(min_length=1, max_length=512)
    label: str = Field(min_length=1, max_length=256)
    graph_selected_ref: str | None = Field(default=None, max_length=512)
    graph_context: BoundedGraphContext | None = None


class FocusBase(MetricsProvenanceModel):
    navigation: NavigationRef
    label: str = Field(min_length=1, max_length=256)
    requested_availability: Literal["live", "durable", "either"]
    time_range: TimeRange
    aggregation: Literal["raw", "summary", "trend"]


class RunFocus(FocusBase):
    subject_kind: Literal["run"] = "run"
    run_id: str = Field(min_length=1, max_length=256)


class ExecutionFocus(FocusBase):
    subject_kind: Literal["execution"] = "execution"
    run_id: str = Field(min_length=1, max_length=256)
    agent_id: str | None = None
    graph_id: str | None = None
    swarm_id: str | None = None

    @model_validator(mode="after")
    def exactly_one_execution_subject(self) -> "ExecutionFocus":
        if sum(value is not None for value in (self.agent_id, self.graph_id, self.swarm_id)) != 1:
            raise ValueError(
                "invalid_focus: execution requires exactly one of agent_id, graph_id, swarm_id"
            )
        return self


class EvalFocus(FocusBase):
    subject_kind: Literal["eval"] = "eval"
    eval_ref: str = Field(min_length=1, max_length=512)
    run_id: str | None = None


class TraceFocus(FocusBase):
    subject_kind: Literal["trace"] = "trace"
    trace_id: str = Field(min_length=1, max_length=128)
    span_id: str | None = None


class SessionFocus(FocusBase):
    subject_kind: Literal["session"] = "session"
    session_id: str = Field(min_length=1, max_length=256)


class EntityFocus(FocusBase):
    subject_kind: Literal["entity"] = "entity"
    entity_ref: str = Field(min_length=1, max_length=512)


class LiveFocus(FocusBase):
    subject_kind: Literal["live"] = "live"


class SystemFocus(FocusBase):
    subject_kind: Literal["system"] = "system"


MetricFocus = Annotated[
    Union[
        RunFocus, ExecutionFocus, EvalFocus, TraceFocus,
        SessionFocus, EntityFocus, LiveFocus, SystemFocus,
    ],
    Field(discriminator="subject_kind"),
]

MeasurementState = Literal[
    "live_not_persisted", "durable_as_of", "still_arriving",
    "no_durable_measurement", "source_unavailable", "source_deleted",
    "source_inaccessible",
]


class MetricResult(MetricsProvenanceModel):
    measurement_state: MeasurementState
    source_class: str = Field(min_length=1, max_length=128)
    evidence_at: datetime | None = None
    last_updated_at: datetime | None = None
    completeness: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str | None = Field(default=None, max_length=512)
    next_action: str | None = Field(default=None, max_length=512)


class MetricMeasurement(MetricsProvenanceModel):
    ok: bool
    focus: MetricFocus | None = None
    navigation: NavigationRef | None = None
    measurement: MetricResult | None = None
    error_code: Literal["invalid_focus", "source_unavailable"] | None = None


__all__ = [
    "BoundedGraphContext", "EntityFocus", "EvalFocus", "ExecutionFocus",
    "FocusBase", "LiveFocus", "MetricFocus", "MetricMeasurement", "MetricResult",
    "MeasurementState", "NavigationRef", "RunFocus", "SessionFocus", "SystemFocus",
    "TimeRange", "TraceFocus",
]

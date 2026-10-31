"""Strict public DTOs for Metrics authoring tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(_Strict): pass


class MetricDefinitionDTO(_Strict):
    """Public wire representation of an authorable metric definition."""
    id: str
    name: str
    description: str = ""
    metric_type: str = "gauge"
    unit: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    composite_formula: str | None = None
    domain: str = "general"
    category: str = "uncategorized"
    source_brick: str | None = None
    input_tool: str | None = None
    format: str = "number"
    bounds: tuple[float, float] | None = None
    thresholds: dict[str, float] = Field(default_factory=dict)


class DefinitionCreate(MetricDefinitionDTO): pass
class DefinitionInput(_Strict): definition: DefinitionCreate
class DefinitionPatch(_Strict):
    name: str | None = None
    description: str | None = None
    metric_type: str | None = None
    unit: str | None = None
    dimensions: list[str] | None = None
    tags: list[str] | None = None
    composite_formula: str | None = None
    domain: str | None = None
    category: str | None = None
    source_brick: str | None = None
    input_tool: str | None = None
    format: str | None = None
    bounds: tuple[float, float] | None = None
    thresholds: dict[str, float] | None = None
class UpdateDefinitionInput(_Strict):
    metric_id: str
    updates: DefinitionPatch
class DeleteDefinitionInput(_Strict): metric_id: str
class SetBaselineInput(_Strict):
    metric_id: str
    tag: str
    values: dict[str, float]
class AuthoringStatusOutput(_Strict):
    enabled: bool
    env_var: str
class DefineMetricOutput(_Strict):
    ok: bool
    id: str | None = None
    persisted: bool | None = None
    error: str | None = None
class UpdateDefinitionOutput(_Strict):
    ok: bool
    id: str | None = None
    definition: MetricDefinitionDTO | None = None
    error: str | None = None
class DeleteDefinitionOutput(_Strict):
    ok: bool
    id: str | None = None
    deleted: bool | None = None
    error: str | None = None
class SetBaselineOutput(_Strict):
    ok: bool
    metric_id: str | None = None
    tag: str | None = None
    values: dict[str, float] | None = None
    created_at: str | None = None
    error: str | None = None

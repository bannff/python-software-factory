"""Pydantic DTOs for canonical Graph run/evidence reads."""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints

from ..runtime.models import TaxonomyEdgeSpec


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunInput(_Input):
    run_id: str
    backend: str = ""


class TopologyInput(RunInput):
    model_config = ConfigDict(extra="forbid", strict=True)

    run_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
    ]
    limit: int = Field(default=200, ge=1, le=200)


class FindingsInput(RunInput):
    app: str = ""
    limit: int = 50
    taxonomy_edges: list[TaxonomyEdgeSpec] | None = None


class CountsInput(RunInput):
    labels: list[str] | str | None = None


class SummaryInput(RunInput):
    taxonomy_edges: list[TaxonomyEdgeSpec] | None = None
    count_labels: list[str] | str | None = None


class RecentFindingsInput(_Input):
    severity: str = ""
    app: str = ""
    run_id: str = ""
    limit: int = 50
    taxonomy_edges: list[TaxonomyEdgeSpec] | None = None
    backend: str = ""


class TargetAppInput(_Input):
    target_app: str
    run_id: str = ""
    backend: str = ""


class LimitInput(_Input):
    limit: int = 100
    backend: str = ""


class RunLimitInput(RunInput):
    limit: int = 50


class RowsData(BaseModel):
    rows: list[dict[str, JsonValue]]
    count: int
    error: str | None = None
    available: list[str] | None = None


class TopologyData(BaseModel):
    run_id: str
    nodes: list[dict[str, JsonValue]]
    edges: list[dict[str, JsonValue]]
    node_count: int
    edge_count: int
    error: str | None = None
    available: list[str] | None = None


class CountsData(BaseModel):
    run_id: str
    labels: list[str]
    counts: dict[str, int]
    total: int
    error: str | None = None
    available: list[str] | None = None


class SummaryData(BaseModel):
    run: dict[str, JsonValue]
    suspected_count: int
    finding_count: int
    finding_verdicts: dict[str, int]
    exploit_count: int
    endpoints_discovered: int
    target_app: str
    error: str | None = None
    available: list[str] | None = None


class TargetAppData(BaseModel):
    found: bool
    target_app: str
    run_id: str
    entity: dict[str, JsonValue] | None = None
    error: str | None = None
    available: list[str] | None = None

"""Strict Pydantic DTOs for ML Observatory projections."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict


class _DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(_DTO):
    pass


class ObservatorySummaryOutput(_DTO):
    population_state: str | None
    health: str
    overview: dict[str, Any]
    sources: list[dict[str, Any]]
    training_runs: list[dict[str, Any]]
    learning_runs: list[dict[str, Any]]
    models: list[dict[str, Any]]
    attention: list[dict[str, Any]]
    series: list[dict[str, Any]]
    experiments: list[dict[str, Any]]
    fine_tuning_jobs: list[dict[str, Any]]
    message: str | None = None


class ObservatoryLineageOutput(_DTO):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    missing_links: list[dict[str, Any]]
    truncated: bool
    truncated_nodes: int
    dropped_edges: int
    max_nodes: int
    sources: list[dict[str, Any]]

"""Concrete outputs for Foreman's command, dependency, and scaffold tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PolyCommandOutput(DTO):
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    error: str | None = None


class DependencyResolution(DTO):
    requested: list[str]
    required: list[str]
    resolved: list[str]
    not_found: list[str]
    python_packages: list[str]
    adapter_imports: list[str]
    used_cache: bool


class BaseSuggestion(DTO):
    base: str
    connects_to: list[str]
    overlap_count: int


class CreateProjectOutput(DTO):
    status: str
    error: str | None = None
    path: str | None = None
    bricks: DependencyResolution | None = None
    files_created: list[str] | None = None
    available_bases: list[str] | None = None
    suggested_bases: list[BaseSuggestion] | None = None
    resolved_components: list[str] | None = None


class SyncBrickResult(DTO):
    brick: str
    status: str
    pip_packages: list[str] | None = None
    unmapped_imports: list[str] | None = None


class SyncBrickDepsOutput(DTO):
    status: str
    dry_run: bool
    total_bricks: int
    updated: int
    unchanged: int
    unmapped_imports: list[str]
    bricks: list[SyncBrickResult]

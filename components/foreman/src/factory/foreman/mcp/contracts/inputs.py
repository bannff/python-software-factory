"""Flat, strict ingress DTOs for Foreman MCP tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    pass


class GuardianCheckInput(DTO):
    workspace_root: str | None = None
    max_lines: int = 200
    file_size_mode: str = "strict"
    base_sha: str | None = None


class CreateNamedInput(DTO):
    name: str


class WorkspaceInput(DTO):
    workspace_root: str | None = None


class WriteIndexInput(WorkspaceInput):
    output_path: str | None = None


class ResolveDependenciesInput(WorkspaceInput):
    bricks: list[str]
    include_adapters: list[str] | None = None


class CreateProjectInput(ResolveDependenciesInput):
    name: str
    description: str = ""


class SyncBrickDepsInput(WorkspaceInput):
    bricks: list[str] | None = None
    dry_run: bool = False

"""Strict Pydantic v2 contracts for uncategorized Blueprint generation tools."""
from __future__ import annotations

from .contracts_base import JsonObject, JsonOutput, StrictInput


class ProjectInput(StrictInput):
    project_name: str


class DockerfileInput(ProjectInput):
    target: str = "docker"


class GenerateAllInput(DockerfileInput):
    pass


class ArtifactOutput(JsonOutput):
    found: bool = True
    project: str
    content: str | None = None
    error: str | None = None


class DockerfileOutput(ArtifactOutput):
    target: str
    bases: list[str] | None = None


class ComposeOutput(ArtifactOutput):
    services: list[str] | None = None
    infra_deps: list[str] | None = None


class EnvOutput(ArtifactOutput):
    infra_services: list[str] | None = None


class GenerateAllOutput(JsonOutput):
    found: bool = True
    project: str
    target: str
    bases: list[str] | None = None
    components_count: int | None = None
    infra_services: list[str] | None = None
    artifacts: dict[str, str] | None = None
    error: str | None = None


class ProjectInfoOutput(JsonOutput):
    found: bool = True
    name: str
    description: str | None = None
    bases: list[str] | None = None
    components: list[str] | None = None
    scripts: JsonObject | None = None
    infra_services: list[str] | None = None
    error: str | None = None


class GenerateCdkInput(StrictInput):
    specs: list[JsonObject]
    project_name: str = "factory"


class PipelineInput(StrictInput):
    renderer: str = "github_actions"
    project_name: str = "factory"
    stages: list[str] | None = None


class RenderedOutput(JsonOutput):
    project: str
    renderer: str | None = None
    files: dict[str, str]
    entry_point: str
    metadata: JsonObject


__all__ = [
    "ArtifactOutput", "ComposeOutput", "DockerfileInput", "DockerfileOutput", "EnvOutput",
    "GenerateAllInput", "GenerateAllOutput", "GenerateCdkInput", "PipelineInput",
    "ProjectInfoOutput", "ProjectInput", "RenderedOutput",
]

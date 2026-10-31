"""Typed but intentionally uncategorized Blueprint generation MCP tools."""
from __future__ import annotations

from typing import Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, typed

from .operational_contracts import (
    ArtifactOutput, ComposeOutput, DockerfileInput, DockerfileOutput, EnvOutput,
    GenerateAllInput, GenerateAllOutput, GenerateCdkInput, PipelineInput,
    ProjectInfoOutput, ProjectInput, RenderedOutput,
)
from ..runtime.deploy.generator import DeployGenerator
from ..runtime.runtime import BlueprintRuntime


def register(mcp: Any, get_generator: Callable[[], DeployGenerator],
             get_runtime: Callable[[], BlueprintRuntime]) -> None:
    """Register generation tools without assigning a new MCP category."""

    @mcp.tool()
    @typed(input_model=DockerfileInput, output_model=DockerfileOutput)
    def blueprint_generate_dockerfile(project_name: str, target: str = "docker") -> ToolResult[DockerfileOutput]:
        try:
            generator, info = get_generator(), None
            content = generator.generate_dockerfile(project_name, target)
            info = generator.introspect(project_name)
            return {"project": project_name, "target": target, "bases": info.bases, "content": content}
        except FileNotFoundError as error:
            return {"found": False, "project": project_name, "target": target, "error": str(error)}

    @mcp.tool()
    @typed(input_model=ProjectInput, output_model=ComposeOutput)
    def blueprint_generate_compose(project_name: str) -> ToolResult[ComposeOutput]:
        try:
            generator = get_generator()
            content, info = generator.generate_compose_services(project_name), generator.introspect(project_name)
            return {"project": project_name, "services": list(info.scripts),
                    "infra_deps": info.infra_services, "content": content}
        except FileNotFoundError as error:
            return {"found": False, "project": project_name, "error": str(error)}

    @mcp.tool()
    @typed(input_model=ProjectInput, output_model=ArtifactOutput)
    def blueprint_generate_makefile(project_name: str) -> ToolResult[ArtifactOutput]:
        try:
            return {"project": project_name, "content": get_generator().generate_makefile(project_name)}
        except FileNotFoundError as error:
            return {"found": False, "project": project_name, "error": str(error)}

    @mcp.tool()
    @typed(input_model=ProjectInput, output_model=EnvOutput)
    def blueprint_generate_env(project_name: str) -> ToolResult[EnvOutput]:
        try:
            generator = get_generator()
            content, info = generator.generate_env_example(project_name), generator.introspect(project_name)
            return {"project": project_name, "infra_services": info.infra_services, "content": content}
        except FileNotFoundError as error:
            return {"found": False, "project": project_name, "error": str(error)}

    @mcp.tool()
    @typed(input_model=GenerateAllInput, output_model=GenerateAllOutput)
    def blueprint_generate_all(project_name: str, target: str = "docker") -> ToolResult[GenerateAllOutput]:
        try:
            generator = get_generator()
            artifacts, info = generator.generate_all(project_name, target), generator.introspect(project_name)
            return {"project": project_name, "target": target, "bases": info.bases,
                    "components_count": len(info.components), "infra_services": info.infra_services,
                    "artifacts": artifacts}
        except FileNotFoundError as error:
            return {"found": False, "project": project_name, "target": target, "error": str(error)}

    @mcp.tool()
    @typed(input_model=ProjectInput, output_model=ProjectInfoOutput)
    def blueprint_introspect_project(project_name: str) -> ToolResult[ProjectInfoOutput]:
        try:
            info = get_generator().introspect(project_name)
            return {"name": info.name, "description": info.description, "bases": info.bases,
                    "components": info.components, "scripts": info.scripts,
                    "infra_services": info.infra_services}
        except FileNotFoundError as error:
            return {"found": False, "name": project_name, "error": str(error)}

    @mcp.tool()
    @typed(input_model=GenerateCdkInput, output_model=RenderedOutput)
    def blueprint_generate_cdk(specs: list[dict], project_name: str = "factory") -> ToolResult[RenderedOutput]:
        output = get_runtime().generate_cdk(specs, project_name)
        return {"project": project_name, "files": output.files, "entry_point": output.entry_point,
                "metadata": output.metadata}

    @mcp.tool()
    @typed(input_model=PipelineInput, output_model=RenderedOutput)
    def blueprint_generate_pipeline(renderer: str = "github_actions", project_name: str = "factory",
                                    stages: list[str] | None = None) -> ToolResult[RenderedOutput]:
        output = get_runtime().generate_pipeline(renderer, project_name, stages)
        return {"project": project_name, "renderer": renderer, "files": output.files,
                "entry_point": output.entry_point, "metadata": output.metadata}

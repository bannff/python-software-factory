"""Tests for blueprint deployment artifact generation."""

from pathlib import Path

import pytest

from factory.blueprint.runtime.deploy.introspect import introspect_project, ProjectInfo
from factory.blueprint.runtime.deploy.generator import DeployGenerator
from factory.blueprint.runtime.deploy.templates import (
    render_dockerfile,
    render_compose_services,
    render_makefile,
    render_env_example,
)


@pytest.fixture
def workspace_root():
    """Get workspace root (assumes tests run from workspace root)."""
    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / "workspace.toml").exists():
            return parent
    pytest.skip("Cannot find workspace root")


@pytest.fixture
def project_info(workspace_root):
    """Introspect the companion_x project."""
    return introspect_project(workspace_root, "companion_x")


class TestIntrospect:
    def test_finds_bases(self, project_info):
        assert "mcp_server" in project_info.bases
        assert "flet_dashboard" in project_info.bases

    def test_finds_components(self, project_info):
        assert "agent" in project_info.components
        assert "cache" in project_info.components

    def test_finds_scripts(self, project_info):
        # companion_x has no scripts defined
        assert isinstance(project_info.scripts, dict)

    def test_missing_project_raises(self, workspace_root):
        with pytest.raises(FileNotFoundError):
            introspect_project(workspace_root, "nonexistent_project")


class TestDockerfile:
    def test_standard_target(self, project_info):
        content = render_dockerfile(project_info, "docker")
        assert "FROM python:" in content
        assert "uv build" in content
        assert "companion_x" in content

    def test_lambda_target(self, project_info):
        content = render_dockerfile(project_info, "lambda")
        assert "ecr.aws/lambda" in content
        assert "companion_x" in content


class TestCompose:
    def test_generates_services(self, project_info):
        content = render_compose_services(project_info)
        assert "companion_x" in content
        assert isinstance(content, str)

    def test_includes_deps(self, project_info):
        content = render_compose_services(project_info)
        assert isinstance(content, str)


class TestMakefile:
    def test_has_targets(self, project_info):
        content = render_makefile(project_info)
        assert "make dev" in content
        assert "make stop" in content
        assert "docker compose" in content


class TestEnvExample:
    def test_renders(self, project_info):
        content = render_env_example(project_info)
        assert isinstance(content, str)


class TestGenerator:
    def test_generate_all(self, workspace_root):
        gen = DeployGenerator(workspace_root)
        artifacts = gen.generate_all("companion_x")
        assert "Dockerfile" in artifacts
        assert "docker-compose.services.yml" in artifacts
        assert "Makefile" in artifacts
        assert ".env.example" in artifacts

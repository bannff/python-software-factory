"""Deployment artifact generator.

Reads a project's pyproject.toml to discover which bases are wired,
then generates appropriate deployment artifacts (Dockerfile, compose,
Makefile, .env) based on the project's actual brick graph.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .introspect import ProjectInfo, introspect_project
from .templates import (
    render_dockerfile,
    render_compose_services,
    render_makefile,
    render_env_example,
)


class DeployGenerator:
    """Generates deployment artifacts for factory projects."""

    TARGETS = ("docker", "lambda", "ecs")

    def __init__(self, workspace_root: Path | None = None) -> None:
        self._root = workspace_root or Path(os.environ.get("WORKSPACE_ROOT", "."))

    def introspect(self, project_name: str) -> ProjectInfo:
        """Introspect a project's brick graph."""
        return introspect_project(self._root, project_name)

    def generate_dockerfile(
        self, project_name: str, target: str = "docker"
    ) -> str:
        """Generate a Dockerfile for the project."""
        info = self.introspect(project_name)
        return render_dockerfile(info, target)

    def generate_compose_services(self, project_name: str) -> str:
        """Generate docker-compose service entries for the project."""
        info = self.introspect(project_name)
        return render_compose_services(info)

    def generate_makefile(self, project_name: str) -> str:
        """Generate a Makefile for the project."""
        info = self.introspect(project_name)
        return render_makefile(info)

    def generate_env_example(self, project_name: str) -> str:
        """Generate .env.example from blueprint settings."""
        info = self.introspect(project_name)
        return render_env_example(info)

    def generate_all(self, project_name: str, target: str = "docker") -> dict[str, str]:
        """Generate all deployment artifacts."""
        return {
            "Dockerfile": self.generate_dockerfile(project_name, target),
            "docker-compose.services.yml": self.generate_compose_services(project_name),
            "Makefile": self.generate_makefile(project_name),
            ".env.example": self.generate_env_example(project_name),
        }

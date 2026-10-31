"""Blueprint runtime — service discovery, configuration, and IaC generation."""

from __future__ import annotations

import os
from typing import Any

from .ports import (
    ServiceHealth,
    InfraBlueprint,
    NormalizedResource,
    RenderedOutput,
    IaCRenderer,
    PipelineRenderer,
)
from .normalizer import normalize_spec
from .resolver import resolve


# Default service URLs (overridable via FACTORY_* env vars)
_DEFAULT_SERVICES: dict[str, str] = {
    "postgres": "postgresql://factory:factory@localhost:5432/factory",
    "neo4j": "bolt://localhost:7687",
    "redis": "redis://localhost:6379/0",
    "keycloak": "http://localhost:8080",
    "seaweedfs": "http://localhost:9333",
    "chromadb": "http://localhost:8000",
    "celery": "redis://localhost:6379/1",
    "dagster": "http://localhost:3000",
    "phoenix": "http://localhost:6006",
}

_ENV_MAP: dict[str, str] = {
    "postgres": "FACTORY_POSTGRES_URL",
    "neo4j": "FACTORY_NEO4J_URL",
    "redis": "FACTORY_REDIS_URL",
    "keycloak": "FACTORY_KEYCLOAK_URL",
    "seaweedfs": "FACTORY_SEAWEED_URL",
    "chromadb": "FACTORY_CHROMA_URL",
    "celery": "FACTORY_CELERY_BROKER_URL",
    "dagster": "FACTORY_DAGSTER_URL",
    "phoenix": "FACTORY_PHOENIX_URL",
}


class BlueprintRuntime:
    """Runtime for infrastructure configuration and IaC generation."""

    def __init__(self) -> None:
        self._services: dict[str, str] = {}
        self._initialize_services()

    def _initialize_services(self) -> None:
        """Initialize service registry from env vars with defaults."""
        for name, default_url in _DEFAULT_SERVICES.items():
            env_key = _ENV_MAP.get(name, f"FACTORY_{name.upper()}_URL")
            self._services[name] = os.environ.get(env_key, default_url)

    @staticmethod
    def available_backends() -> list[str]:
        return ["env", "file"]

    def get_service_url(self, name: str) -> str | None:
        return self._services.get(name)

    def list_services(self) -> list[str]:
        return list(self._services.keys())

    def get_all_urls(self) -> dict[str, str]:
        return self._services.copy()

    def update_service_url(self, name: str, url: str) -> None:
        """Update one process-local service URL through the runtime boundary."""
        self._services[name] = url

    def health_check(self, name: str | None = None) -> dict[str, ServiceHealth]:
        if name:
            url = self._services.get(name)
            return {
                name: ServiceHealth(
                    name=name, healthy=url is not None, url=url or "",
                    error=None if url else "Service not found",
                )
            }
        return {
            svc: ServiceHealth(name=svc, healthy=True, url=url)
            for svc, url in self._services.items()
        }

    def generate_cdk(
        self,
        specs: list[dict[str, Any]],
        project_name: str = "factory",
        renderer_type: str = "cdk",
    ) -> RenderedOutput:
        """Normalize specs → resolve blueprint → render CDK output."""
        resources: list[NormalizedResource] = []
        for spec in specs:
            brick = spec.get("brick", "unknown")
            raw = spec.get("spec", spec)
            resources.extend(normalize_spec(brick, raw))

        blueprint = resolve(resources)
        renderer = self._get_iac_renderer(renderer_type)
        return renderer.render(blueprint, project_name)

    def generate_pipeline(
        self,
        renderer_type: str = "github_actions",
        project_name: str = "factory",
        stages: list[str] | None = None,
    ) -> RenderedOutput:
        """Generate CI/CD pipeline configuration."""
        renderer = self._get_pipeline_renderer(renderer_type)
        return renderer.render(project_name, stages)

    def _get_iac_renderer(self, renderer_type: str) -> IaCRenderer:
        if renderer_type == "cdk":
            from .renderers.cdk import CdkRenderer
            return CdkRenderer()
        raise ValueError(f"Unknown IaC renderer: {renderer_type}")

    def _get_pipeline_renderer(self, renderer_type: str) -> PipelineRenderer:
        if renderer_type == "github_actions":
            from .renderers.github_actions import GitHubActionsRenderer
            return GitHubActionsRenderer()
        raise ValueError(f"Unknown pipeline renderer: {renderer_type}")

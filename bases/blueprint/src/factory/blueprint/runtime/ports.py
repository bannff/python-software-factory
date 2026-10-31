"""Blueprint ports — Protocol interfaces for config backends and IaC renderers.

Defines abstract interfaces for configuration backends, service discovery,
and infrastructure-as-code rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


# ── Service Discovery ──────────────────────────────────────────────

@dataclass
class ServiceHealth:
    """Health status for a service."""
    name: str
    healthy: bool
    url: str
    latency_ms: float | None = None
    error: str | None = None


@runtime_checkable
class ConfigBackendPort(Protocol):
    """Port: Configuration backend (env, file, SSM, etc.)"""
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def list_keys(self, prefix: str = "") -> list[str]: ...
    def health_check(self) -> bool: ...


@runtime_checkable
class ServiceDiscoveryPort(Protocol):
    """Port: Service discovery backend."""
    def register(self, name: str, url: str, metadata: dict[str, Any] | None = None) -> None: ...
    def deregister(self, name: str) -> None: ...
    def discover(self, name: str) -> str | None: ...
    def list_services(self) -> list[str]: ...
    def health_check(self, name: str) -> ServiceHealth: ...


# ── IaC Data Model ─────────────────────────────────────────────────

@dataclass
class NormalizedResource:
    """A single normalized AWS resource from an infrastructure_spec()."""
    brick: str
    service: str
    construct: str
    props: dict[str, Any] = field(default_factory=dict)
    logical_id: str = ""


@dataclass
class IamStatement:
    """A minimal IAM policy statement."""
    effect: str = "Allow"
    actions: list[str] = field(default_factory=list)
    resource: str = "*"


@dataclass
class InfraBlueprint:
    """Resolved infrastructure blueprint ready for rendering."""
    resources: list[NormalizedResource] = field(default_factory=list)
    shared_iam_statements: list[IamStatement] = field(default_factory=list)
    vpc_required: bool = False
    services_used: set[str] = field(default_factory=set)


@dataclass
class RenderedOutput:
    """Output from a renderer — a dict of filepath → content."""
    files: dict[str, str] = field(default_factory=dict)
    entry_point: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Renderer Protocols ─────────────────────────────────────────────

@runtime_checkable
class IaCRenderer(Protocol):
    """Protocol for infrastructure-as-code renderers."""
    @property
    def renderer_type(self) -> str: ...
    def render(self, blueprint: InfraBlueprint, project_name: str) -> RenderedOutput: ...
    def validate(self, blueprint: InfraBlueprint) -> list[str]: ...


@runtime_checkable
class PipelineRenderer(Protocol):
    """Protocol for CI/CD pipeline renderers."""
    @property
    def renderer_type(self) -> str: ...
    def render(self, project_name: str, stages: list[str] | None = None) -> RenderedOutput: ...

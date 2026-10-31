"""FastMCP server interface for metrics tools."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .authoring import AuthoringManager, authoring_enabled
from .mcp import authoring, deterministic, deterministic_stats, operational, prompts, resources, seed
from .mcp.views import register as register_views
from .runtime.adapters.memory import InMemoryMetricsComputer, InMemoryMetricsStore
from .runtime.runtime import MetricsRuntime


def get_runtime() -> MetricsRuntime:
    """Create the default in-memory Metrics runtime."""
    config_dir = Path(os.environ.get("METRICS_CONFIG_DIR", "./config/metrics"))
    config_dir.mkdir(parents=True, exist_ok=True)
    runtime = MetricsRuntime(store=InMemoryMetricsStore(), computer=InMemoryMetricsComputer())
    defs_dir = config_dir / "definitions"
    if defs_dir.exists():
        import yaml
        from .runtime.models import MetricDefinition
        for path in sorted(defs_dir.glob("*.yaml")):
            try:
                runtime.register_definition(MetricDefinition.model_validate(yaml.safe_load(path.read_text()) or {}))
            except Exception:
                pass
    from .mcp.seed import _DEFAULT_DEFINITIONS
    from .runtime.models import MetricDefinition
    for raw in _DEFAULT_DEFINITIONS:
        if runtime.get_definition(raw["id"]) is None:
            runtime.register_definition(MetricDefinition(**raw))
    return runtime


def _register_tools(registry: Any, runtime: MetricsRuntime) -> None:
    enabled = authoring_enabled()
    manager = AuthoringManager(Path(os.environ.get("METRICS_CONFIG_DIR", "./config/metrics"))) if enabled else None
    deterministic.register(registry, runtime)
    deterministic_stats.register(registry, runtime)
    operational.register(registry, runtime)
    authoring.register(registry, runtime, manager, enabled)
    seed.register(registry, runtime)
    register_views(registry)


def create_tool_catalog(runtime: MetricsRuntime | None = None) -> Any:
    """Create the transport-neutral Metrics tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("metrics-module")
    _register_tools(catalog, active_runtime)
    resources.register(catalog, active_runtime)
    prompts.register(catalog, active_runtime)
    return catalog


def create_mcp_server(runtime: MetricsRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)

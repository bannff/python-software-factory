"""Native MCP v2 server interface exposing workflow tools, resources, and prompts.

This module is the public MCP surface. It must not contain domain logic.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from factory.mcp_utils.interface import set_service
from factory.workflow.authoring import AuthoringManager, authoring_enabled
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.mcp import (
    deterministic,
    loop_deterministic,
    loop_operational,
    operational,
    execution,
    authoring,
    register_resources,
    register_prompts,
    register_views,
)

logger = logging.getLogger(__name__)


def _config_dir() -> Path:
    """Resolve the configured workflow config directory."""
    return Path(os.environ.get("WORKFLOW_CONFIG_DIR", "./config"))


def _config_provenance() -> dict[str, Any]:
    """Report whether the runtime is built from a real deployment settings.yaml."""
    config_dir = _config_dir().resolve()
    settings_path = config_dir / "settings.yaml"
    if settings_path.exists():
        return {"configured": True, "config_dir": str(config_dir)}
    if os.environ.get("WORKFLOW_CONFIG_DIR") is not None:
        reason = (
            "WORKFLOW_CONFIG_DIR is set but has no settings.yaml: "
            "WorkflowRuntime construction raises WorkflowError, so a caller that "
            "reaches the workflow runtime directly fails loudly instead of "
            "getting an empty execution-engine registry; through the MCP "
            "aggregator the workflow brick is registered unhealthy with zero "
            "workflow tools while /api/health still answers 200"
        )
    else:
        reason = (
            "WORKFLOW_CONFIG_DIR is unset and ./config has no settings.yaml: "
            "running on default Settings with an empty execution-engine registry"
        )
    return {
        "configured": False,
        "config_dir": str(config_dir),
        "missing": str(settings_path),
        "reason": reason,
    }


def _missing_settings_hint(config_dir: Path) -> str:
    """Actionable remediation naming the env var and, when present, the template."""
    live = (config_dir / "settings.yaml").resolve()
    template = (config_dir / "settings.yaml.example").resolve()
    if template.exists():
        source = f"copy the tracked deployment template: cp {template} {live}"
    else:
        source = (
            f"provide {live} (each project config dir ships a tracked "
            "settings.yaml.example template — see projects/*/config/)"
        )
    return (
        f"{source}, or set WORKFLOW_CONFIG_DIR to the directory holding this "
        "deployment's settings.yaml"
    )


def get_runtime() -> WorkflowRuntime:
    """Create a default WorkflowRuntime from environment / defaults.

    A missing settings.yaml under an explicitly configured WORKFLOW_CONFIG_DIR
    raises ``WorkflowError`` here (issue #34) rather than returning a runtime
    with an empty execution-engine registry, whose absence only surfaces later
    as a confusing ``ValueError: unknown execution engine: <id>``. What an
    operator observes depends on the caller: reaching this function directly
    raises, while through the MCP aggregator the error is caught during brick
    registration, so the workflow brick is reported unhealthy with zero tools
    and ``/api/health`` still answers 200. With WORKFLOW_CONFIG_DIR unset the
    module default (``./config``) may legitimately be absent, so boot continues
    with a loud warning instead.
    """
    from factory.workflow.runtime.models import Settings
    from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage
    from factory.workflow.runtime.execution.adapters import create_executor
    from factory.workflow.runtime.operations import WorkflowError

    config_dir = _config_dir()
    if (config_dir / "settings.yaml").exists():
        return WorkflowRuntime.from_config_dir(config_dir)
    env_value = os.environ.get("WORKFLOW_CONFIG_DIR")
    if env_value is not None:
        raise WorkflowError(
            f"WORKFLOW_CONFIG_DIR={env_value} has no settings.yaml (expected "
            f"{(config_dir / 'settings.yaml').resolve()}): raising instead of "
            "continuing with an empty execution-engine registry, which cannot "
            "enroll any engine and fails later as 'unknown execution engine: "
            "<id>' (through the MCP aggregator this surfaces as the workflow "
            "brick unhealthy with zero workflow tools); "
            f"{_missing_settings_hint(config_dir)}"
        )
    logger.warning(
        "WORKFLOW_CONFIG_DIR is unset and %s has no settings.yaml: starting the "
        "library default with an EMPTY execution-engine registry — any engine "
        "enrollment will fail with 'unknown execution engine: <id>'; %s",
        (config_dir / "settings.yaml").resolve(), _missing_settings_hint(config_dir),
    )
    settings = Settings()
    db_path = config_dir / "data" / "workflow.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    storage = SqliteWorkflowStorage(db_path)
    storage.init_schema()
    return WorkflowRuntime(
        config_dir=config_dir,
        settings=settings,
        settings_raw=settings.model_dump(),
        workflows=[],
        storage=storage,
        executor=create_executor(),
    )


def _register_tools(registry: Any, runtime: WorkflowRuntime) -> None:
    enabled = authoring_enabled(runtime.settings_raw)
    manager = AuthoringManager(runtime.config_dir) if enabled else None
    runtime.set_runtime_flags(authoring_enabled=enabled, running_mode="stdio")
    deterministic.register(registry, runtime)
    loop_deterministic.register(registry, runtime)
    loop_operational.register(registry, runtime)
    set_service("workflow_loop_reconciler", runtime.reconcile_loops)
    operational.register(registry, runtime)
    execution.register(registry, runtime)
    from factory.workflow.runtime.background_recovery import schedule_background_recovery
    set_service(
        "workflow_background_reconciler",
        lambda submit: schedule_background_recovery(runtime, submit),
    )
    authoring.register(registry, runtime, manager)
    register_views(registry, runtime)


def create_tool_catalog(runtime: WorkflowRuntime | None = None) -> Any:
    """Create the transport-neutral Workflow tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("workflow-module")
    _register_tools(catalog, active_runtime)
    register_resources(catalog, active_runtime)
    register_prompts(catalog, active_runtime)
    return catalog


def create_mcp_server(runtime: WorkflowRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    """Delegate capability reporting to the configured runtime."""
    capabilities = get_runtime().get_capabilities()
    capabilities["config"] = _config_provenance()
    return capabilities


def health_check() -> dict[str, Any]:
    """Report actual configured storage, executor, and durable readiness."""
    health = get_runtime().health_check()
    health["config"] = _config_provenance()
    return health


def describe_config_schema() -> dict[str, Any]:
    """Return the runtime's authoritative Pydantic schemas."""
    return get_runtime().describe_config_schema()

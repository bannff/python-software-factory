"""Machine learning MCP server - exposes ML tracking and fine-tuning via FastMCP."""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.server import make_lazy_runner

from .runtime.runtime import get_runtime, TrackingRuntime
from .mcp import (
    can_pipeline_tool, can_lifecycle_tools, deterministic, operational, authoring,
    resources, prompts, views, finetuning_tools, timeseries_tools, inference_tools,
    passport_tools, dashboard_summary, observatory_tools, supervision_tools,
)


def _resolved_runtime(
    runtime: TrackingRuntime | None, passport_service: Any,
) -> TrackingRuntime | None:
    return (
        runtime or TrackingRuntime(passport_service=passport_service)
        if passport_service is not None else runtime
    )


def _register_tools(
    registry: Any, runtime: TrackingRuntime | None, passport_service: Any,
    can_lifecycle_service: Any, supervision_service: Any = None,
) -> None:
    get_current = lambda: runtime if runtime is not None else get_runtime()
    deterministic.register(registry, get_current)
    finetuning_tools.register(registry, get_current)
    timeseries_tools.register(registry, get_current)
    inference_tools.register(registry, get_current)
    passport_tools.register(registry, (lambda: passport_service) if passport_service is not None else None)
    can_pipeline_tool.register(registry, get_current)
    can_lifecycle_tools.register(
        registry, get_current,
        (lambda: can_lifecycle_service) if can_lifecycle_service is not None else None,
    )
    supervision_tools.register(
        registry, get_current,
        (lambda: supervision_service) if supervision_service is not None else None,
    )
    operational.register(registry, get_current)
    authoring.register(registry, get_current)
    dashboard_summary.register(registry)
    observatory_tools.register(registry, get_current)
    views.register(registry)


def create_tool_catalog(
    runtime: TrackingRuntime | None = None, *, passport_service: Any = None,
    can_lifecycle_service: Any = None, supervision_service: Any = None,
) -> Any:
    """Create the transport-neutral Machine Learning tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    resolved = _resolved_runtime(runtime, passport_service)
    catalog = ToolCatalog("factory-machine-learning")
    _register_tools(catalog, resolved, passport_service, can_lifecycle_service, supervision_service)
    get_current = lambda: resolved if resolved is not None else get_runtime()
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server(
    runtime: TrackingRuntime | None = None, *, passport_service: Any = None,
    can_lifecycle_service: Any = None, supervision_service: Any = None,
) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(
        runtime, passport_service=passport_service,
        can_lifecycle_service=can_lifecycle_service,
        supervision_service=supervision_service,
    )


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for machine_learning brick."""
    return {
        "name": "machine_learning",
        "version": "2.0.0",
        "backends": ["memory", "mlflow", "tensorboard"],
        "finetuning_backends": ["memory"],
        "features": [
            "experiment_tracking", "run_management", "metrics_logging",
            "model_registry", "finetuning", "lora", "qlora", "model_export",
            "dataset_artifact_training_input", "ml_observatory",
            "immutable_model_passports",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for machine_learning brick."""
    try:
        runtime = get_runtime()
        return {"healthy": True, "experiments": len(runtime.health_check())}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def describe_config_schema() -> dict[str, Any]:
    """Describe machine_learning configuration schema."""
    return {
        "type": "object",
        "properties": {
            "backend": {"type": "string", "enum": ["memory", "mlflow", "tensorboard"]},
            "finetuning_backend": {"type": "string", "enum": ["memory"]},
            "model_passport_root": {
                "type": "string", "env": "ML_MODEL_PASSPORT_ROOT",
                "description": "Required durable trust root for ModelPassport operations",
            },
            "lightgbm_model_root": {
                "type": "string", "env": "ML_LIGHTGBM_MODEL_ROOT",
                "description": "Optional model subdirectory beneath the passport root",
            },
            "lnn_model_root": {
                "type": "string", "env": "ML_LNN_MODEL_ROOT",
                "description": "Dedicated LNN subdirectory beneath the passport root",
            },
        },
    }

get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()

"""Framework-neutral Evals tool catalog."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.server import make_lazy_runner

from .mcp import (
    deterministic,
    evaluator_tools,
    experiment_tools,
    operational,
    prompts,
    record_verification_tools,
    review_tools,
    resources,
    run_record_tools,
    seed,
    serialization_tools,
    session_tools,
    simulation_tools,
    sop_tools,
    tool_chaos_tools,
    ui_explorer_tools,
    ui_scenario_tools,
)
from .mcp.views import register as register_views
from .runtime.runtime import EvalsRuntime, get_runtime


def _register_tools(registry: Any, runtime: EvalsRuntime) -> None:
    get_current = lambda: runtime
    deterministic.register(registry, get_current)
    operational.register(registry, get_current)
    run_record_tools.register(registry)
    review_tools.register(registry)
    record_verification_tools.register(registry)
    ui_scenario_tools.register(registry, get_current)
    ui_explorer_tools.register(registry, get_current)
    evaluator_tools.register(registry, get_current)
    experiment_tools.register(registry, get_current)
    simulation_tools.register(registry, get_current)
    serialization_tools.register(registry, get_current)
    tool_chaos_tools.register(registry, get_current)
    session_tools.register(registry, get_current)
    sop_tools.register(registry, get_current)
    seed.register(registry, get_current)
    register_views(registry)


def create_tool_catalog(runtime: EvalsRuntime | None = None) -> Any:
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-evals")
    _register_tools(catalog, active_runtime)
    get_current = lambda: active_runtime
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server(runtime: EvalsRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    return {
        "name": "evals",
        "version": "2.0.0",
        "backends": ["custom", "strands", "ui_explorer"],
        "features": [
            "benchmark_suites", "eval_runs", "metrics_collection",
            "result_comparison", "ui_exploration", "direct_evaluator_invocation",
            "multi_evaluator_batch", "immutable_run_records",
            "immutable_review_acceptance",
            "immutable_record_pointer_verification", "storage_first_projection",
            "eval_sop_workflow", "strands_experiments", "experiment_generation",
            "declarative_agent_config", "actor_simulation", "experiment_serialization",
            "tool_chaos",
        ],
    }


def health_check() -> dict[str, Any]:
    try:
        runtime = get_runtime()
        return {"healthy": True, "suites": len(runtime.suites)}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}


def describe_config_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "adapter": {"type": "string", "enum": ["custom", "strands"]},
            "output_dir": {"type": "string", "description": "Results output directory"},
            "persistence": {
                "type": "string", "enum": ["noop", "graph"], "default": "noop",
                "description": "Explicit durable persistence backend",
            },
        },
    }


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()

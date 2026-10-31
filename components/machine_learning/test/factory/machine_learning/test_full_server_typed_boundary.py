"""Whole-surface Pydantic v2 boundary proof for Machine Learning MCP tools."""
from __future__ import annotations

from typing import get_type_hints

import pytest
from pydantic import BaseModel

from factory.machine_learning.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult


TOOLS = {
    "can_get_model_info", "can_predict_failure", "can_predict_failure_warm_compat",
    "can_run_full_pipeline", "ml_acquire_chronos2_backbone", "ml_cleanup_checkpoints",
    "ml_compare_timeseries", "ml_configure_training_defaults", "ml_continue_timeseries",
    "ml_create_finetuning_job", "ml_describe_config_schema", "ml_export_model",
    "ml_get_capabilities", "ml_get_dashboard_summary", "ml_get_finetuning_job",
    "ml_get_job_status", "ml_get_learning_run", "ml_get_learning_run_artifacts",
    "ml_get_learning_run_timeline", "ml_get_learning_summary", "ml_get_model_passport",
    "ml_get_model_passport_by_model", "ml_get_observatory_lineage",
    "ml_get_observatory_summary", "ml_get_run_regression", "ml_get_training_run",
    "ml_get_views", "ml_health_check", "ml_issue_can_passports",
    "ml_list_checkpoints", "ml_list_finetuning_jobs", "ml_list_finetuning_methods",
    "ml_list_learning_runs", "ml_list_stage_artifacts", "ml_list_timeseries_models",
    "ml_list_training_runs", "ml_predict_neural_passport", "ml_predict_timeseries",
    "ml_pause_training", "ml_project_can_pipeline_result", "ml_promote_can_passports",
    "ml_register_base_model", "ml_resume_training", "ml_run_can_cold_conformance",
    "ml_sample_timeseries", "ml_start_finetuning_job", "ml_stop_at_checkpoint",
    "ml_stop_finetuning_job", "ml_train_can_portfolio", "ml_train_timeseries",
    "ml_adjust_hyperparam", "ml_verify_and_promote_can_passport",
    "ml_verify_and_promote_lightgbm_passport",
    "tracking_create_experiment", "tracking_end_run", "tracking_get_experiment",
    "tracking_get_run", "tracking_list_experiments", "tracking_log_metrics",
    "tracking_log_params", "tracking_start_run",
}


@pytest.mark.asyncio
async def test_fresh_server_exposes_exactly_sixty_one_strict_typed_tools() -> None:
    tools = await create_mcp_server().list_tools()
    names = [tool.name for tool in tools]

    assert set(names) == TOOLS
    assert len(names) == len(set(names)) == 61
    assert not any(name.endswith("_v2") for name in names)

    for tool in tools:
        function = tool.fn
        input_model = function._mcp_input_model
        output_model = function._mcp_output_model
        assert function._mcp_category in {"deterministic", "operational", "authoring"}
        for model in (input_model, output_model):
            assert issubclass(model, BaseModel)
            assert model.__module__.startswith("factory.machine_learning.")
            assert model.model_config["extra"] == "forbid"
        result_type = get_type_hints(function)["return"]
        metadata = result_type.__pydantic_generic_metadata__
        assert metadata["origin"] is ToolResult
        assert metadata["args"] == (output_model,)

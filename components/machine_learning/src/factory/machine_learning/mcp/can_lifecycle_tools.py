"""Thin MCP registration for attempt-idempotent ML training lifecycle terminals.

The five static verbs keep their CAN-prefixed names for API stability;
coordinator event names resolve through the ``lifecycle_family`` spec
registry — no domain-conditioned strings live in this file (epic #124 S1).
"""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from factory.mcp_utils.interface import ToolResult, fail, ok, operational

from ..runtime.can_lifecycle_composition import create_can_lifecycle
from .can_lifecycle_models import (
    IssueCanPassportsInput,
    IssueCanPassportsOutput,
    ProjectCanPipelineResultInput,
    ProjectCanPipelineResultOutput,
    PromoteCanPassportsInput,
    PromoteCanPassportsOutput,
    RunCanColdConformanceInput,
    RunCanColdConformanceOutput,
    TrainCanPortfolioInput,
    TrainCanPortfolioOutput,
)


def _terminal_result(raw: dict[str, Any], output: type[BaseModel]) -> ToolResult[Any]:
    """Map runtime terminal errors to envelopes; completed terminals remain data."""
    if raw.get("status") != "completed":
        return fail(str(raw.get("error", "CAN lifecycle terminal failed")))
    return ok(output.model_validate(raw))


def register(
    mcp: Any, get_runtime: Callable[[], Any],
    service_factory: Callable[[], Any] | None = None,
) -> None:
    """Register five static workflow-facing MCP invocation names."""
    factory = service_factory or (lambda: create_can_lifecycle(get_runtime()))

    @mcp.tool(name="ml_train_can_portfolio")
    @operational(
        input_model=TrainCanPortfolioInput, output_model=TrainCanPortfolioOutput,
    )
    def train_can_portfolio(
        attempt_id: str, dataset_request: dict[str, Any],
        model_family: str = "lightgbm", top_n_can_ids: int = 5,
        training_config: dict[str, Any] | None = None,
        model_config: dict[str, Any] | None = None,
        experiment_name: str = "",
    ) -> ToolResult[TrainCanPortfolioOutput]:
        """Replay Dataset and train one durable declared CAN model family."""
        return _terminal_result(factory().train({
            "attempt_id": attempt_id, "dataset_request": dataset_request,
            "model_family": model_family, "top_n_can_ids": top_n_can_ids,
            "training_config": training_config or {}, "model_config": model_config,
            "experiment_name": experiment_name,
        }), TrainCanPortfolioOutput)

    @mcp.tool(name="ml_issue_can_passports")
    @operational(
        input_model=IssueCanPassportsInput, output_model=IssueCanPassportsOutput,
    )
    def issue_can_passports(
        attempt_id: str, training_terminal_ref: dict[str, Any],
        evaluation_pointers: list[dict[str, Any]],
    ) -> ToolResult[IssueCanPassportsOutput]:
        """Issue revision-one passports from an exact trusted training ref."""
        return _terminal_result(factory().issue({
            "attempt_id": attempt_id,
            "training_terminal_ref": training_terminal_ref,
            "evaluation_pointers": evaluation_pointers,
        }), IssueCanPassportsOutput)

    @mcp.tool(name="ml_run_can_cold_conformance")
    @operational(
        input_model=RunCanColdConformanceInput,
        output_model=RunCanColdConformanceOutput,
    )
    def run_can_cold_conformance(
        attempt_id: str, passport_refs: list[dict[str, Any]],
    ) -> ToolResult[RunCanColdConformanceOutput]:
        """Generate stored cold-conformance receipts for exact passports."""
        return _terminal_result(factory().conform({
            "attempt_id": attempt_id, "passport_refs": passport_refs,
        }), RunCanColdConformanceOutput)

    @mcp.tool(name="ml_promote_can_passports")
    @operational(
        input_model=PromoteCanPassportsInput,
        output_model=PromoteCanPassportsOutput,
    )
    def promote_can_passports(
        attempt_id: str, conformance_receipt_refs: list[dict[str, Any]],
    ) -> ToolResult[PromoteCanPassportsOutput]:
        """Promote only evidence reloaded from exact conformance receipts."""
        return _terminal_result(factory().promote({
            "attempt_id": attempt_id,
            "conformance_receipt_refs": conformance_receipt_refs,
        }), PromoteCanPassportsOutput)

    @mcp.tool(name="ml_project_can_pipeline_result")
    @operational(
        input_model=ProjectCanPipelineResultInput,
        output_model=ProjectCanPipelineResultOutput,
    )
    def project_can_pipeline_result(
        attempt_id: str, training_terminal_ref: dict[str, Any],
        promotion_terminal_ref: dict[str, Any],
    ) -> ToolResult[ProjectCanPipelineResultOutput]:
        """Project from exact trusted training and promotion terminal refs."""
        return _terminal_result(factory().project({
            "attempt_id": attempt_id,
            "training_terminal_ref": training_terminal_ref,
            "promotion_terminal_ref": promotion_terminal_ref,
        }), ProjectCanPipelineResultOutput)


__all__ = ["register"]

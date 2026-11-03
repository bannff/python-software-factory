"""Typed tools to list/update/delete base models and delete fine-tuning jobs.

Base models stay in the process-local registry owned by ``authoring``; mutations
are authoring-gated like ``ml_register_base_model``.
"""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import (
    ToolResult, TypedToolFailure, authoring as authoring_decorator, deterministic, fail, ok,
    operational,
)

from ..runtime.authoring_policy import authoring_enabled
from ..runtime.runtime import TrackingRuntime
from . import authoring
from .authoring_contracts import (
    BaseModelDeletedOutput, BaseModelEntry, BaseModelNameInput, BaseModelOutput,
    BaseModelsOutput, EmptyInput, UpdateBaseModelInput,
)
from .operational_contracts import FineTuningJobOutput, JobIdInput


def _entry(row: dict[str, Any]) -> BaseModelEntry:
    return BaseModelEntry(**{k: row[k] for k in BaseModelEntry.model_fields})


def _row(name: str) -> dict[str, Any]:
    row = authoring._model_registry.get(name)
    if row is None:
        raise TypedToolFailure("base_model_not_found", name)
    return row


def register(mcp: Any, get_runtime: Callable[[], TrackingRuntime]) -> None:
    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=BaseModelsOutput)
    def ml_list_base_models() -> ToolResult[BaseModelsOutput]:
        rows = sorted(authoring._model_registry.values(), key=lambda r: r["name"])
        return ok(BaseModelsOutput(count=len(rows), models=[_entry(r) for r in rows]))

    @mcp.tool()
    @authoring_decorator(input_model=UpdateBaseModelInput, output_model=BaseModelOutput)
    def ml_update_base_model(
        name: str, model_id: str | None = None, description: str | None = None,
        recommended_method: str | None = None,
    ) -> ToolResult[BaseModelOutput]:
        if not authoring_enabled():
            return fail(authoring._DISABLED)
        row = _row(name)
        changes = {"model_id": model_id, "description": description,
                   "recommended_method": recommended_method}
        row.update({k: v for k, v in changes.items() if v is not None})
        return ok(BaseModelOutput(model=_entry(row)))

    @mcp.tool()
    @authoring_decorator(input_model=BaseModelNameInput, output_model=BaseModelDeletedOutput)
    def ml_delete_base_model(name: str) -> ToolResult[BaseModelDeletedOutput]:
        """Refused with ``base_model_in_use`` while any fine-tuning job uses it."""
        if not authoring_enabled():
            return fail(authoring._DISABLED)
        row = _row(name)
        in_use = {name, row["model_id"]}
        if any(j.base_model in in_use for j in get_runtime().get_finetuner().list_jobs()):
            raise TypedToolFailure("base_model_in_use", name)
        del authoring._model_registry[name]
        return ok(BaseModelDeletedOutput(name=name, deleted=True))

    @mcp.tool()
    @operational(input_model=JobIdInput, output_model=FineTuningJobOutput)
    def ml_delete_finetuning_job(job_id: str) -> ToolResult[FineTuningJobOutput]:
        """Refused with ``job_running`` while the job runs; checkpoints are kept."""
        finetuner = get_runtime().get_finetuner()
        job = finetuner.get_job(job_id)
        if job is None:
            raise TypedToolFailure("job_not_found", job_id)
        delete = getattr(finetuner, "delete_job", None)
        if delete is None:
            raise TypedToolFailure("job_delete_unsupported", job_id)
        try:
            delete(job_id)
        except ValueError as exc:
            raise TypedToolFailure(str(exc), job_id) from exc
        return ok(FineTuningJobOutput(id=job_id, status="deleted"))

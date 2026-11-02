"""Typed MCP tools to register, inspect, edit and delete training datasets."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, deterministic, ok, operational

from ..runtime.dataset_registry import REGISTRY, DatasetRecord
from ..runtime.runtime import TrackingRuntime
from .dataset_contracts import (
    DatasetDeletedOutput, DatasetDTO, DatasetIdInput, DatasetOutput, DatasetsOutput,
    EmptyDatasetInput, RegisterDatasetInput, UpdateDatasetInput,
)


def _dto(record: DatasetRecord) -> DatasetDTO:
    return DatasetDTO(**asdict(record))


def _used_uris(get_runtime: Callable[[], TrackingRuntime]) -> list[str]:
    jobs = get_runtime().get_finetuner().list_jobs()
    return [j.training_input.dataset_uri for j in jobs if j.training_input is not None]


def register(mcp: Any, get_runtime: Callable[[], TrackingRuntime]) -> None:
    """Register dataset CRUD; failures surface as typed ``dataset_*`` codes."""
    @mcp.tool()
    @deterministic(input_model=EmptyDatasetInput, output_model=DatasetsOutput)
    def ml_list_datasets() -> ToolResult[DatasetsOutput]:
        items = REGISTRY.list()
        return ok(DatasetsOutput(count=len(items), datasets=[_dto(i) for i in items]))

    @mcp.tool()
    @deterministic(input_model=DatasetIdInput, output_model=DatasetOutput)
    def ml_get_dataset(dataset_id: str) -> ToolResult[DatasetOutput]:
        return ok(DatasetOutput(dataset=_dto(REGISTRY.get(dataset_id))))

    @mcp.tool()
    @operational(input_model=RegisterDatasetInput, output_model=DatasetOutput)
    def ml_register_dataset(
        name: str, uri: str, manifest_uri: str, digest: str, view_name: str,
        view_schema_version: str, description: str = "",
    ) -> ToolResult[DatasetOutput]:
        record = REGISTRY.register(DatasetRecord(
            name, uri, manifest_uri, digest, view_name, view_schema_version, description,
        ))
        return ok(DatasetOutput(dataset=_dto(record)))

    @mcp.tool()
    @operational(input_model=UpdateDatasetInput, output_model=DatasetOutput)
    def ml_update_dataset(
        dataset_id: str, description: str, expected_revision: int,
    ) -> ToolResult[DatasetOutput]:
        return ok(DatasetOutput(dataset=_dto(
            REGISTRY.update(dataset_id, expected_revision, description))))

    @mcp.tool()
    @operational(input_model=DatasetIdInput, output_model=DatasetDeletedOutput)
    def ml_delete_dataset(dataset_id: str) -> ToolResult[DatasetDeletedOutput]:
        """Refused with ``dataset_in_use`` while any fine-tuning job reads it."""
        REGISTRY.delete(dataset_id, _used_uris(get_runtime))
        return ok(DatasetDeletedOutput(dataset_id=dataset_id, deleted=True))

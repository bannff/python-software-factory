"""Strict typed boundaries for ML dataset tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyDatasetInput(_Strict):
    pass


class DatasetIdInput(_Strict):
    dataset_id: str = Field(min_length=2, max_length=64)


class RegisterDatasetInput(_Strict):
    name: str = Field(min_length=2, max_length=64)
    uri: str = Field(min_length=1, max_length=2048)
    manifest_uri: str = Field(min_length=1, max_length=2048)
    digest: str = Field(min_length=1, max_length=80)
    view_name: str = Field(min_length=1, max_length=128)
    view_schema_version: str = Field(min_length=1, max_length=32)
    description: str = Field(default="", max_length=2000)


class UpdateDatasetInput(_Strict):
    dataset_id: str = Field(min_length=2, max_length=64)
    description: str = Field(max_length=2000)
    expected_revision: int = Field(ge=1)


class DatasetDTO(_Strict):
    dataset_id: str
    uri: str
    manifest_uri: str
    digest: str
    view_name: str
    view_schema_version: str
    description: str
    revision: int


class DatasetOutput(_Strict):
    dataset: DatasetDTO


class DatasetsOutput(_Strict):
    count: int
    datasets: list[DatasetDTO]


class DatasetDeletedOutput(_Strict):
    dataset_id: str
    deleted: bool

"""Typed request contract for dataset generation jobs."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_validator

from .approval_models import DatasetApprovalBinding
from .base import (
    DatasetExecutionPolicy, DatasetInputRef, DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef, _normalize_digest, _require_non_empty,
)
from .blueprint_models import DatasetBlueprintBinding
from .scenario_models import ScenarioPackGenerationInput


class DatasetGenerationRequest(BaseModel):
    """A versioned declarative request for a dataset bundle."""
    recipe_uri: str
    recipe_digest: str
    input_artifacts: list[DatasetInputRef] = Field(default_factory=list)
    allowed_local_roots: tuple[Path, ...] = Field(
        default_factory=tuple,
        description=(
            "Caller-authorized local roots for referenced edge sensor payload files. "
            "Paths are compared lexically before no-follow reads."
        ),
    )
    context_snapshot: DatasetSnapshotRef
    tool_schema_snapshot: DatasetToolSchemaSnapshotRef
    requested_views: list[str] = Field(default_factory=lambda: ["default"], min_length=1, max_length=10)
    execution_policy: DatasetExecutionPolicy = Field(default_factory=DatasetExecutionPolicy)
    scenario_generation: ScenarioPackGenerationInput | None = None
    blueprint_binding: DatasetBlueprintBinding | None = None
    approval_binding: DatasetApprovalBinding | None = None
    idempotency_key: str | None = None
    schema_version: str = "1.0"

    @field_validator("recipe_uri")
    @classmethod
    def _validate_recipe_uri(cls, value: str) -> str:
        return _require_non_empty(value, "Dataset recipe URI")

    @field_validator("recipe_digest")
    @classmethod
    def _validate_recipe_digest(cls, value: str) -> str:
        return _normalize_digest(value, "dataset recipe")

    @field_validator("requested_views")
    @classmethod
    def _validate_requested_views(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for view in value:
            name = view.strip()
            if not name:
                raise ValueError("Requested dataset view must be non-empty")
            if name in cleaned:
                raise ValueError("Requested dataset views must be unique")
            cleaned.append(name)
        return cleaned

    @field_validator("allowed_local_roots", mode="before")
    @classmethod
    def _validate_allowed_local_roots(cls, value: Any) -> tuple[str, ...]:
        """Keep a canonical lexical allowlist without probing filesystem paths."""
        if value is None:
            return ()
        roots: list[Path] = []
        for item in value:
            root = Path(item)
            if not root.is_absolute() or ".." in root.parts:
                raise ValueError("Allowed local roots must be absolute paths without traversal")
            normalized = Path(os.path.abspath(root))
            if normalized in roots:
                raise ValueError("Allowed local roots must be unique")
            roots.append(normalized)
        return tuple(str(root) for root in roots)

    @computed_field(return_type=str)
    @property
    def context_snapshot_uri(self) -> str:
        return self.context_snapshot.uri

    @computed_field(return_type=str)
    @property
    def context_snapshot_digest(self) -> str:
        return self.context_snapshot.digest

    @computed_field(return_type=str)
    @property
    def tool_schema_snapshot_uri(self) -> str:
        return self.tool_schema_snapshot.uri

    @computed_field(return_type=str)
    @property
    def tool_schema_snapshot_digest(self) -> str:
        return self.tool_schema_snapshot.digest

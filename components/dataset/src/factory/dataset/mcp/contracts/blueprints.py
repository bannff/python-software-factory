"""Strict DTOs for Dataset blueprint MCP tools."""
from __future__ import annotations

from typing import Literal

from pydantic import StrictStr

from .base import InputDTO, OutputDTO
from ...runtime.blueprint_models import DatasetBlueprintBinding, DatasetBlueprintRef
from ...runtime.blueprint_results import DatasetBlueprintConflict


class ValidateBlueprintInput(InputDTO):
    blueprint_json: StrictStr
    storage_root: StrictStr | None = None


class MaterializeBlueprintInput(InputDTO):
    blueprint_json: StrictStr
    approval_id: StrictStr
    approval_revision: StrictStr
    approval_digest: StrictStr
    storage_root: StrictStr | None = None


class BlueprintValidationOutput(OutputDTO):
    status: Literal["validated"]
    binding: DatasetBlueprintBinding
    recipe_uri: StrictStr
    stage_names: list[StrictStr]
    record_schema: Literal["generic"]


class BlueprintMaterializationOutput(OutputDTO):
    status: Literal["queued", "conflict"]
    blueprint: DatasetBlueprintRef | None = None
    job_id: StrictStr | None = None
    submitted_at: StrictStr | None = None
    conflict: DatasetBlueprintConflict | None = None


BlueprintValidationOutput.model_rebuild()
BlueprintMaterializationOutput.model_rebuild()

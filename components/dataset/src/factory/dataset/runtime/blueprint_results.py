"""Result contracts for blueprint validation, publication, and submission."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import model_validator

from .blueprint_models import DatasetBlueprintBinding, DatasetBlueprintRef
from .scenario_pack_models import FrozenModel


class DatasetBlueprintConflict(FrozenModel):
    identity: str
    version: str
    existing_digest: str
    requested_digest: str
    reason: str = "DatasetBlueprint identity/version already has different content"


class DatasetBlueprintPublishResult(FrozenModel):
    status: Literal["published", "existing", "conflict"]
    ref: DatasetBlueprintRef | None = None
    conflict: DatasetBlueprintConflict | None = None

    @model_validator(mode="after")
    def _shape(self) -> "DatasetBlueprintPublishResult":
        if (self.status == "conflict") != (self.conflict is not None):
            raise ValueError("DatasetBlueprint publish conflict shape is invalid")
        if (self.status != "conflict") != (self.ref is not None):
            raise ValueError("DatasetBlueprint publish reference shape is invalid")
        return self


class DatasetBlueprintValidation(FrozenModel):
    status: Literal["validated"] = "validated"
    binding: DatasetBlueprintBinding
    recipe_uri: str
    stage_names: tuple[str, ...]
    record_schema: Literal["generic"] = "generic"


class DatasetBlueprintMaterialization(FrozenModel):
    status: Literal["queued", "conflict"]
    blueprint: DatasetBlueprintRef | None = None
    job_id: str | None = None
    submitted_at: datetime | None = None
    conflict: DatasetBlueprintConflict | None = None

    @model_validator(mode="after")
    def _shape(self) -> "DatasetBlueprintMaterialization":
        is_conflict = self.status == "conflict"
        if is_conflict != (self.conflict is not None):
            raise ValueError("DatasetBlueprint materialization conflict shape is invalid")
        if is_conflict == (self.blueprint is not None and self.job_id is not None):
            raise ValueError("DatasetBlueprint materialization job shape is invalid")
        return self

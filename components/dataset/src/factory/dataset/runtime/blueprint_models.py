"""Frozen contracts for Dataset-first materialization blueprints."""
from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from .scenario_models import ScenarioPackRef
from .scenario_pack_models import FrozenModel, digest, text, token

_FORBIDDEN_KEYS = frozenset({
    "validator", "validators", "evaluator_code", "script", "command",
    "callable", "promotion", "promote", "accept", "executable", "import",
    "import_target", "entrypoint", "module",
})


class _VersionedRef(FrozenModel):
    id: str
    version: str
    digest: str

    @field_validator("id", "version")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "blueprint reference ID/version")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "blueprint reference")


class DatasetRecipeRef(_VersionedRef):
    pass


class DatasetStageRef(_VersionedRef):
    pass


class DatasetOutputSchemaRef(_VersionedRef):
    pass


class DatasetCapabilityRef(_VersionedRef):
    pass


class DatasetSourceEvidenceRef(_VersionedRef):
    artifact: ScenarioPackRef


class DatasetQualityPolicyRef(FrozenModel):
    id: str
    revision: str
    digest: str

    @field_validator("id", "revision")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "quality policy ID/revision")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "quality policy")


class BlueprintResolution(FrozenModel):
    recipe_uri: str
    stage_names: tuple[str, ...]
    record_schema: str
    generator_adapter: str
    generator_version: str


class DatasetBlueprint(FrozenModel):
    identity: str
    version: str
    recipe: DatasetRecipeRef
    stages: tuple[DatasetStageRef, ...] = Field(min_length=1)
    output_schema: DatasetOutputSchemaRef
    source_evidence: tuple[DatasetSourceEvidenceRef, ...] = Field(min_length=1)
    capabilities: tuple[DatasetCapabilityRef, ...] = Field(min_length=1)
    quality_policy: DatasetQualityPolicyRef
    generation_seed: int = Field(strict=True, ge=0, le=2**63 - 1)
    requested_views: tuple[str, ...] = Field(default=("default",), min_length=1, max_length=10)

    @model_validator(mode="before")
    @classmethod
    def _reject_executable_shapes(cls, value):
        def walk(node) -> None:
            if isinstance(node, dict):
                for key, child in node.items():
                    normalized = str(key).strip().lower().replace("-", "_")
                    if normalized in _FORBIDDEN_KEYS:
                        raise ValueError(f"Executable blueprint field is forbidden: {key}")
                    walk(child)
            elif isinstance(node, (list, tuple)):
                for child in node:
                    walk(child)
        walk(value)
        return value

    @field_validator("identity", "version")
    @classmethod
    def _identity(cls, value: str) -> str:
        return token(value, "DatasetBlueprint identity/version")

    @field_validator("source_evidence", "capabilities")
    @classmethod
    def _sort_set_refs(cls, value: tuple):
        keys = [(item.id, item.version, item.digest) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("Blueprint set-like references must be unique")
        return tuple(item for _, item in sorted(zip(keys, value, strict=True)))

    @field_validator("requested_views")
    @classmethod
    def _views(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(token(item, "requested view") for item in value)
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Requested views must be unique")
        return cleaned


class _BlueprintIdentityRef(FrozenModel):
    identity: str
    version: str
    digest: str

    @field_validator("identity", "version")
    @classmethod
    def _identity(cls, value: str) -> str:
        return token(value, "DatasetBlueprint identity/version")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "DatasetBlueprint")


class DatasetBlueprintBinding(_BlueprintIdentityRef):
    quality_policy: DatasetQualityPolicyRef


class DatasetBlueprintLineage(FrozenModel):
    binding: DatasetBlueprintBinding
    recipe: DatasetRecipeRef
    stages: tuple[DatasetStageRef, ...]
    output_schema: DatasetOutputSchemaRef
    source_evidence: tuple[DatasetSourceEvidenceRef, ...]
    capabilities: tuple[DatasetCapabilityRef, ...]


class DatasetBlueprintRef(_BlueprintIdentityRef):
    uri: str

    @field_validator("uri")
    @classmethod
    def _uri(cls, value: str) -> str:
        return text(value, "DatasetBlueprint URI")


class DatasetHumanApprovalRef(FrozenModel):
    id: str
    revision: str
    digest: str

    @field_validator("id", "revision")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "human approval ID/revision")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "human approval")


class DatasetHumanApprovalRecord(FrozenModel):
    id: str
    revision: str
    blueprint_digest: str
    quality_policy: DatasetQualityPolicyRef

    @field_validator("id", "revision")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "human approval record ID/revision")

    @field_validator("blueprint_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "approved blueprint")

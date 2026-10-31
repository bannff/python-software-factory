"""Frozen ScenarioPack references, publication results, and lineage."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .scenario_pack_models import (
    FrozenModel, ScenarioAssumption, ScenarioSource, digest, text, token,
)


class ScenarioPackRef(FrozenModel):
    identity: str
    version: str
    uri: str
    digest: str

    @field_validator("identity", "version")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "ScenarioPack reference identity/version")

    @field_validator("uri")
    @classmethod
    def _uri(cls, value: str) -> str:
        return text(value, "ScenarioPack reference URI")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "scenario pack")


class ScenarioPackGenerationInput(FrozenModel):
    scenario_pack: ScenarioPackRef
    generator_adapter: str
    generator_version: str
    seed: int = Field(strict=True, ge=0, le=2**63 - 1)

    @field_validator("generator_adapter", "generator_version")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "scenario generator field")


class ScenarioEpisodeLineage(FrozenModel):
    episode_id: str
    episode_digest: str
    scenario_id: str
    outcome_id: str
    ordinal: int = Field(strict=True, ge=0)
    derived_seed: int = Field(strict=True, ge=0, le=2**63 - 1)
    split_group: str
    claim_ids: tuple[str, ...] = Field(min_length=1)
    assumption_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("episode_id", "scenario_id", "outcome_id", "split_group")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "scenario episode lineage field")

    @field_validator("episode_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "scenario episode")


class ScenarioPackLineage(FrozenModel):
    scenario_pack: ScenarioPackRef
    sources: tuple[ScenarioSource, ...]
    assumptions: tuple[ScenarioAssumption, ...]
    generator_adapter: str
    generator_version: str
    seed: int = Field(strict=True, ge=0, le=2**63 - 1)
    episodes: tuple[ScenarioEpisodeLineage, ...] = Field(min_length=1)

    @field_validator("generator_adapter", "generator_version")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "scenario lineage generator field")


class ScenarioPackConflict(FrozenModel):
    identity: str
    version: str
    existing_digest: str
    requested_digest: str
    reason: str = "scenario pack identity/version already has different content"


class ScenarioPackPublishResult(FrozenModel):
    status: Literal["published", "existing", "conflict"]
    ref: ScenarioPackRef | None = None
    conflict: ScenarioPackConflict | None = None

    @model_validator(mode="after")
    def _shape(self) -> "ScenarioPackPublishResult":
        if (self.status == "conflict") != (self.conflict is not None):
            raise ValueError("ScenarioPack publish result conflict shape is invalid")
        if (self.status != "conflict") != (self.ref is not None):
            raise ValueError("ScenarioPack publish result reference shape is invalid")
        return self

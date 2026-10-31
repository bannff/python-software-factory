"""Frozen canonical ScenarioPack content contracts."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def token(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty canonical string")
    if not _TOKEN_RE.fullmatch(value):
        raise ValueError(f"Invalid {label}")
    return value


def text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    return value


def digest(value: str, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        raise ValueError(f"Invalid {label} digest")
    return value


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScenarioSource(FrozenModel):
    source_id: str
    uri: str
    digest: str
    license: str
    version: str

    @field_validator("source_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return token(value, "source ID")

    @field_validator("uri", "license", "version")
    @classmethod
    def _text(cls, value: str) -> str:
        return text(value, "Scenario source field")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "scenario source")


class ScenarioEvidence(FrozenModel):
    evidence_id: str
    source_id: str
    locator: str
    range_start: int = Field(strict=True, ge=0)
    range_end: int = Field(strict=True, gt=0)

    @field_validator("evidence_id", "source_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return token(value, "evidence ID")

    @field_validator("locator")
    @classmethod
    def _locator(cls, value: str) -> str:
        return text(value, "Evidence locator")

    @model_validator(mode="after")
    def _ordered_range(self) -> "ScenarioEvidence":
        if self.range_end <= self.range_start:
            raise ValueError("Evidence range_end must be greater than range_start")
        return self


class ScenarioClaim(FrozenModel):
    claim_id: str
    statement: str
    evidence_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("claim_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return token(value, "claim ID")

    @field_validator("statement")
    @classmethod
    def _statement(cls, value: str) -> str:
        return text(value, "Claim statement")


class ScenarioAssumption(FrozenModel):
    assumption_id: str
    statement: str

    @field_validator("assumption_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return token(value, "assumption ID")

    @field_validator("statement")
    @classmethod
    def _statement(cls, value: str) -> str:
        return text(value, "Assumption statement")


class ScenarioOutcome(FrozenModel):
    outcome_id: str
    definition: str

    @field_validator("outcome_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return token(value, "outcome ID")

    @field_validator("definition")
    @classmethod
    def _definition(cls, value: str) -> str:
        return text(value, "Outcome definition")


class ScenarioStep(FrozenModel):
    role: Literal["system", "user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def _content(cls, value: str) -> str:
        return text(value, "Scenario step content")


class ScenarioDefinition(FrozenModel):
    scenario_id: str
    title: str
    setup: str
    steps: tuple[ScenarioStep, ...] = Field(min_length=1)
    claim_ids: tuple[str, ...] = Field(min_length=1)
    assumption_ids: tuple[str, ...] = Field(min_length=1)
    outcome_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("scenario_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return token(value, "scenario ID")

    @field_validator("title", "setup")
    @classmethod
    def _text(cls, value: str) -> str:
        return text(value, "Scenario definition field")


class ScenarioGenerationRule(FrozenModel):
    adapter: str
    version: str
    episodes_per_outcome: int = Field(default=1, strict=True, ge=1, le=10_000)

    @field_validator("adapter", "version")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "generation rule field")


class ScenarioPackDraft(FrozenModel):
    identity: str
    version: str
    sources: tuple[ScenarioSource, ...] = Field(min_length=1)
    evidence: tuple[ScenarioEvidence, ...] = Field(min_length=1)
    claims: tuple[ScenarioClaim, ...] = Field(min_length=1)
    assumptions: tuple[ScenarioAssumption, ...] = Field(min_length=1)
    outcomes: tuple[ScenarioOutcome, ...] = Field(min_length=1)
    scenarios: tuple[ScenarioDefinition, ...] = Field(min_length=1)
    generation_rule: ScenarioGenerationRule

    @field_validator("identity", "version")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "ScenarioPack identity/version")


class ScenarioPack(ScenarioPackDraft):
    digest: str

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "scenario pack")

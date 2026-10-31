"""Typed boundaries for the S2 supervision verbs (epic #124)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, StrictStr


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PauseTrainingInput(_Input):
    attempt_id: StrictStr
    reason: StrictStr = ""


class StopAtCheckpointInput(_Input):
    attempt_id: StrictStr
    checkpoint_name: StrictStr = ""


class ResumeTrainingInput(_Input):
    attempt_id: StrictStr
    reason: StrictStr = ""


class AdjustHyperparamInput(_Input):
    attempt_id: StrictStr
    hyperparams: dict[str, Any]


class SupervisionActionOutput(_Output):
    schema_version: str = "1.0"
    operation: str
    attempt_id: str
    action: str
    intent_id: str
    intent_sha256: str
    status: str


class AdjustedClaimOutput(_Output):
    schema_version: str = "1.0"
    status: str
    operation: str
    parent_attempt_id: str
    adjusted_attempt_id: str
    adjusted_request_sha256: str
    claim_state: str
    hyperparams: dict[str, Any]


__all__ = [
    "AdjustedClaimOutput", "AdjustHyperparamInput", "PauseTrainingInput",
    "ResumeTrainingInput", "StopAtCheckpointInput", "SupervisionActionOutput",
]

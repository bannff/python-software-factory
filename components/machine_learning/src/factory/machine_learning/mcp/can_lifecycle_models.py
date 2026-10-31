"""Strict typed MCP contracts for the five CAN lifecycle terminals."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..runtime.can_evals_binding import CanEvalsPointer
from ..runtime.can_lifecycle_refs import CanConformanceReceiptRef, CanTerminalRef
from ..runtime.can_lifecycle_results import (
    CanConformanceResult,
    CanPassportResult,
    CanProjectResult,
    CanTrainResult,
)


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _TerminalOutput(_Output):
    schema_version: Literal["1.0"]
    status: Literal["completed"]
    operation: str
    attempt_id: str
    request_sha256: str
    terminal_ref: CanTerminalRef


class TrainCanPortfolioInput(_Input):
    attempt_id: str
    dataset_request: dict[str, Any]
    model_family: str = "lightgbm"
    top_n_can_ids: int = 5
    training_config: dict[str, Any] | None = None
    model_parameters: dict[str, Any] | None = Field(
        default=None, validation_alias="model_config", serialization_alias="model_config",
    )
    experiment_name: str = ""

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        return super().model_dump(by_alias=True, **kwargs)


class IssueCanPassportsInput(_Input):
    attempt_id: str
    training_terminal_ref: CanTerminalRef
    evaluation_pointers: list[CanEvalsPointer]


class RunCanColdConformanceInput(_Input):
    attempt_id: str
    passport_refs: list[dict[str, Any]]


class PromoteCanPassportsInput(_Input):
    attempt_id: str
    conformance_receipt_refs: list[CanConformanceReceiptRef]


class ProjectCanPipelineResultInput(_Input):
    attempt_id: str
    training_terminal_ref: CanTerminalRef
    promotion_terminal_ref: CanTerminalRef


class TrainCanPortfolioOutput(_TerminalOutput, CanTrainResult):
    pass


class IssueCanPassportsOutput(_TerminalOutput, CanPassportResult):
    pass


class RunCanColdConformanceOutput(_TerminalOutput, CanConformanceResult):
    pass


class PromoteCanPassportsOutput(_TerminalOutput, CanPassportResult):
    pass


class ProjectCanPipelineResultOutput(_TerminalOutput, CanProjectResult):
    pass


__all__ = [
    "IssueCanPassportsInput", "IssueCanPassportsOutput",
    "ProjectCanPipelineResultInput", "ProjectCanPipelineResultOutput",
    "PromoteCanPassportsInput", "PromoteCanPassportsOutput",
    "RunCanColdConformanceInput", "RunCanColdConformanceOutput",
    "TrainCanPortfolioInput", "TrainCanPortfolioOutput",
]

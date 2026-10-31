"""Strict MCP contracts for background completion delivery."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..runtime.models import CompletionDelivery, Identifier, Identity
from .contracts import InputDTO, OutputDTO
from .lifecycle_contracts import EnvelopeInput


class CompletionWriteInput(InputDTO):
    tenant_id: Identity
    owner_id: Identity
    session_id: Identifier
    run_id: Identity
    revision: int = Field(ge=1)
    result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: Literal["ok", "failed", "stopped", "interrupted"]
    summary: str = Field(min_length=1, max_length=32_768)


class CompletionAckInput(InputDTO):
    tenant_id: Identity
    owner_id: Identity
    session_id: Identifier
    run_id: Identity
    revision: int = Field(ge=1)
    result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class PendingCompletionsInput(InputDTO):
    session_id: Identifier
    envelope: EnvelopeInput | None = None


class CompletionOutput(OutputDTO):
    completion: CompletionDelivery


class CompletionsOutput(OutputDTO):
    completions: list[CompletionDelivery]


__all__ = [
    "CompletionAckInput", "CompletionOutput", "CompletionWriteInput",
    "CompletionsOutput", "PendingCompletionsInput",
]

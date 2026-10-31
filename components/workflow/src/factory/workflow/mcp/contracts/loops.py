"""Strict MCP contracts for durable Workflow goal and monitor loops."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ...runtime.loop_models import LoopCycleRecord, LoopRecord
from .base import DTO
from .operational import EnvelopeInput


class StartLoopInput(DTO):
    kind: Literal["goal", "monitor"]
    agent_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,127}$")
    objective: str = Field(min_length=1, max_length=16_384)
    cycle_instructions: str = Field(min_length=1, max_length=16_384)
    interval_seconds: int = Field(default=300, ge=15, le=86_400)
    max_cycles: int = Field(default=24, ge=0, le=10_000)
    max_runtime_seconds: int = Field(default=0, ge=0, le=31_536_000)
    loop_id: str | None = Field(
        default=None, pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$",
    )
    envelope: EnvelopeInput | None = None


class LoopRefInput(DTO):
    loop_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    envelope: EnvelopeInput | None = None


class LoopRevisionInput(LoopRefInput):
    expected_revision: int = Field(ge=1)


class LoopCycleRefInput(LoopRefInput):
    cycle: int = Field(ge=1, le=10_000)


class ListLoopsInput(DTO):
    limit: int = Field(default=100, ge=1, le=1000)
    envelope: EnvelopeInput | None = None


class LoopOutput(DTO):
    loop: LoopRecord


class LoopsOutput(DTO):
    loops: list[LoopRecord]


class LoopCycleOutput(DTO):
    cycle: LoopCycleRecord


__all__ = ["ListLoopsInput", "LoopCycleOutput", "LoopCycleRefInput", "LoopOutput",
           "LoopRefInput", "LoopRevisionInput", "LoopsOutput", "StartLoopInput"]

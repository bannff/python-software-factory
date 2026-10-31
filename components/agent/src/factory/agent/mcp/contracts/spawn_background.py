"""Strict contracts for Workflow-owned background persona launch."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .discovery import StrictDTO


class SpawnBackgroundInput(StrictDTO):
    agent_id: str = Field(min_length=1, max_length=128)
    task: str = Field(min_length=1, max_length=100_000)
    context: dict[str, str] | None = Field(default=None, max_length=64)
    launch_id: str | None = Field(
        default=None, min_length=1, max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    output_schema: Literal["loop-cycle-report-v1"] | None = None
    delivery_mode: Literal["origin", "workflow_loop"] = "origin"
    loop_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    loop_cycle: int | None = Field(default=None, ge=1, le=10_000)

    @model_validator(mode="after")
    def _loop_binding(self) -> "SpawnBackgroundInput":
        values = (self.output_schema, self.loop_id, self.loop_cycle)
        if self.delivery_mode == "workflow_loop" and any(v is None for v in values):
            raise ValueError("workflow loop launch binding is incomplete")
        if self.delivery_mode == "origin" and any(v is not None for v in values):
            raise ValueError("origin delivery cannot carry loop launch binding")
        return self


class SpawnBackgroundOutput(StrictDTO):
    run_id: str
    run_key: str
    status: Literal["pending", "running"]
    agent_id: str
    origin_session_id: str



class SteerBackgroundInput(StrictDTO):
    run_id: str = Field(min_length=1, max_length=256)
    send_id: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$",
    )
    content: str = Field(min_length=1, max_length=32_768)


class SteerBackgroundOutput(StrictDTO):
    run_id: str
    send_id: str
    state: Literal["written"]
    revision: int = Field(ge=1)

__all__ = [
    "SpawnBackgroundInput", "SpawnBackgroundOutput",
    "SteerBackgroundInput", "SteerBackgroundOutput",
]

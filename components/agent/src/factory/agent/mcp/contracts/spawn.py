"""Strict MCP contracts for bounded, attempt-local persona spawning."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .discovery import StrictDTO


class SpawnSubagentInput(StrictDTO):
    agent_id: str = Field(min_length=1, max_length=128)
    task: str = Field(min_length=1, max_length=100_000)
    context: dict[str, Any] | None = None


class SpawnSwarmInput(StrictDTO):
    agent_ids: list[str]
    task: str = Field(min_length=1, max_length=100_000)
    context: dict[str, Any] | None = None


class SpawnEdgeInput(StrictDTO):
    source: str = Field(alias="from", min_length=1, max_length=128)
    target: str = Field(alias="to", min_length=1, max_length=128)


class SpawnGraphInput(StrictDTO):
    agent_ids: list[str]
    edges: list[SpawnEdgeInput]
    task: str = Field(min_length=1, max_length=100_000)
    context: dict[str, Any] | None = None


class SpawnOutput(StrictDTO):
    success: bool
    kind: Literal["subagent", "swarm", "graph"]
    status: Literal["completed", "rejected", "failed", "timeout"]
    invocation_id: str = ""
    output: str = ""
    error_code: str | None = None
    unknown_agent_ids: list[str] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)


__all__ = [
    "SpawnGraphInput", "SpawnOutput", "SpawnSubagentInput", "SpawnSwarmInput",
]

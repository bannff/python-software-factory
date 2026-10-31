"""Typed CloudFormation MCP contracts for the Sandbox brick."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .contracts import StrictModel


class EnvOnlyRequest(StrictModel):
    env_id: str = Field(min_length=1, max_length=256)


class StackRequest(EnvOnlyRequest):
    stack_name: str = Field(min_length=1, max_length=128)


class DeployStackRequest(StackRequest):
    template_body: str = Field(min_length=1, max_length=1_000_000)
    parameters: dict[str, str] | None = None
    capabilities: list[str] | None = None


class StackSummary(StrictModel):
    name: str = ""
    status: str = ""
    created: str = ""


class DeployStackResult(StrictModel):
    success: bool
    stack_name: str
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = Field(default=0, ge=0)
    stack_outputs: dict[str, str] = Field(default_factory=dict)
    stack_status: str | None = None
    error: str | None = None


class StackListResult(StrictModel):
    stacks: list[StackSummary] = Field(default_factory=list)
    count: int = Field(default=0, ge=0)
    error: str | None = None


class StackDescriptionResult(StrictModel):
    stack_name: str
    status: str
    outputs: dict[str, str] = Field(default_factory=dict)
    creation_time: str = ""
    description: str = ""
    error: str | None = None


class DeleteStackResult(StrictModel):
    success: bool
    stack_name: str


class TranslateCfnRequest(StrictModel):
    template_body: str = Field(min_length=1, max_length=1_000_000)
    mode: Literal["supported", "security"] = "supported"


class TranslateCfnResult(StrictModel):
    template: str
    kept_resources: list[str] = Field(default_factory=list)
    dropped_resources: list[str] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)


__all__ = [
    "DeleteStackResult", "DeployStackRequest", "DeployStackResult",
    "EnvOnlyRequest", "StackDescriptionResult", "StackListResult", "StackRequest",
    "TranslateCfnRequest", "TranslateCfnResult",
]

"""Strict typed contracts for Agent Crew MCP tools.

Client inputs never carry ``tenant_id``/``owner_id`` — authority is ambient,
derived from the authenticated envelope by the lifecycle. Grammar/length
bounds here are defense-in-depth; ``CrewConfig`` re-validates on construction.
"""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from .discovery import StrictDTO

_CrewId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
_PersonaId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9_-]{0,127}$")]
_Scope = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
_Name = Annotated[str, Field(min_length=1, max_length=200)]
_Description = Annotated[str, Field(max_length=2000)]
_Project = Annotated[str, Field(min_length=1, max_length=512)]
_Workspace = Annotated[str, Field(max_length=512)]
_Model = Annotated[str, Field(max_length=256)]
_Triggers = Annotated[
    list[Annotated[str, Field(min_length=1, max_length=64)]], Field(max_length=32),
]
_Revision = Annotated[int, Field(ge=1)]


class CrewListInput(StrictDTO):
    """Zero-argument list of the caller's owner-scoped Crews."""


class CrewIdInput(StrictDTO):
    crew_id: _CrewId


class CrewResolveInput(StrictDTO):
    crew_id: _CrewId
    session_model: _Model = ""


class CrewCreateInput(StrictDTO):
    crew_id: _CrewId
    name: _Name
    persona_id: _PersonaId
    project: _Project
    memory_scope: _Scope
    description: _Description = ""
    workspace: _Workspace = ""
    model: _Model = ""
    triggers: _Triggers = Field(default_factory=list)


class CrewUpdateInput(CrewCreateInput):
    expected_revision: _Revision


class CrewDefaultInput(StrictDTO):
    crew_id: _CrewId
    expected_revision: _Revision


class CrewDeleteInput(CrewDefaultInput):
    pass


class CrewRecordDTO(StrictDTO):
    tenant_id: str
    owner_id: str
    id: str
    name: str
    description: str
    persona_id: str
    project: str
    workspace: str
    memory_scope: str
    model: str
    triggers: list[str]
    revision: int


class CrewOutput(StrictDTO):
    crew: CrewRecordDTO


class CrewsOutput(StrictDTO):
    count: int
    crews: list[CrewRecordDTO]
    default_id: str | None = None


class CrewResolvedOutput(StrictDTO):
    crew_id: str
    persona_id: str
    model_id: str
    project: str
    workspace: str
    memory_scope: str


class CrewDeletedOutput(StrictDTO):
    crew_id: str
    deleted: bool


__all__ = [
    "CrewCreateInput", "CrewDefaultInput", "CrewDeleteInput", "CrewDeletedOutput",
    "CrewIdInput", "CrewListInput", "CrewOutput", "CrewRecordDTO", "CrewResolveInput",
    "CrewResolvedOutput", "CrewUpdateInput", "CrewsOutput",
]

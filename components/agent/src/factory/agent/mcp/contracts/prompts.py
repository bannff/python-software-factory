"""Strict typed contracts for owner-authored prompt MCP tools (authority is ambient)."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .discovery import StrictDTO

_Id = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")]
_Revision = Annotated[int, Field(ge=1)]


class PromptArgDTO(StrictDTO):
    name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
    description: Annotated[str, Field(max_length=500)] = ""
    required: bool = False


class PromptListInput(StrictDTO):
    """Zero-argument list of the caller's authored prompts."""


class PromptAddInput(StrictDTO):
    prompt_id: _Id
    description: Annotated[str, Field(max_length=2000)] = ""
    arguments: Annotated[list[PromptArgDTO], Field(max_length=16)] = []
    template: Annotated[str, Field(min_length=1, max_length=20_000)]


class PromptUpdateInput(StrictDTO):
    prompt_id: _Id
    expected_revision: _Revision
    description: Annotated[str, Field(max_length=2000)] | None = None
    arguments: Annotated[list[PromptArgDTO], Field(max_length=16)] | None = None
    template: Annotated[str, Field(min_length=1, max_length=20_000)] | None = None


class PromptDeleteInput(StrictDTO):
    prompt_id: _Id


class PromptRenderInput(StrictDTO):
    prompt_id: _Id
    arguments: dict[str, str] = Field(default_factory=dict)


class PromptRecordDTO(StrictDTO):
    prompt_id: str
    description: str
    arguments: list[PromptArgDTO]
    template: str
    revision: int
    origin: Literal["authored"] = "authored"
    created_at: str
    updated_at: str


class PromptOutput(StrictDTO):
    prompt: PromptRecordDTO


class PromptsOutput(StrictDTO):
    count: int
    prompts: list[PromptRecordDTO]


class PromptDeletedOutput(StrictDTO):
    prompt_id: str
    deleted: bool


class PromptMessage(StrictDTO):
    role: str
    content: str


class PromptRenderOutput(StrictDTO):
    prompt_id: str
    messages: list[PromptMessage]

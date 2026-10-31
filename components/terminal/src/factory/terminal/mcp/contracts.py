"""Strict terminal MCP contracts."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..runtime.models import TerminalOutputChunk, TerminalSessionRef


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    pass


class OpenInput(DTO):
    shell: str | None = Field(default=None, max_length=512)
    cwd: str | None = Field(default=None, max_length=4096)
    cols: int = Field(default=80, ge=10, le=1000)
    rows: int = Field(default=24, ge=2, le=500)


class SessionInput(DTO):
    session_id: str = Field(pattern=r"^term_[0-9a-f]{32}$")


class WriteInput(SessionInput):
    data: str = Field(max_length=65_536)


class ReadInput(SessionInput):
    timeout_seconds: float = Field(default=0.25, ge=0.0, le=5.0)


class ResizeInput(SessionInput):
    cols: int = Field(ge=10, le=1000)
    rows: int = Field(ge=2, le=500)


class SessionOutput(DTO):
    session: TerminalSessionRef


class SessionsOutput(DTO):
    sessions: list[TerminalSessionRef]


class ShellsOutput(DTO):
    shells: list[str]


class OutputChunk(DTO):
    chunk: TerminalOutputChunk


class MutationOutput(DTO):
    session_id: str
    ok: bool


__all__ = [
    "EmptyInput", "MutationOutput", "OpenInput", "OutputChunk", "ReadInput",
    "ResizeInput", "SessionInput", "SessionOutput", "SessionsOutput",
    "ShellsOutput", "WriteInput",
]

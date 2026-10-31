"""Strict terminal runtime models."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TerminalSpawnSpec(Model):
    shell: str | None = Field(default=None, max_length=512)
    cwd: str | None = Field(default=None, max_length=4096)
    cols: int = Field(default=80, ge=10, le=1000)
    rows: int = Field(default=24, ge=2, le=500)


class TerminalSessionRef(Model):
    session_id: str = Field(pattern=r"^term_[0-9a-f]{32}$")
    shell: str
    cwd: str
    cols: int
    rows: int
    alive: bool


class TerminalOutputChunk(Model):
    session_id: str
    data: str
    eof: bool = False


class TerminalResizeSpec(Model):
    session_id: str
    cols: int = Field(ge=10, le=1000)
    rows: int = Field(ge=2, le=500)


class TerminalCompletionEntry(Model):
    name: str = Field(max_length=512)
    dir: bool = False
    at: int = Field(default=0, ge=0, le=512)
    kind: Literal["sub", "flag"] | None = None
    description: str | None = Field(default=None, max_length=512)
    nospace: bool = False


class TerminalCompletionSpec(Model):
    session_id: str = Field(pattern=r"^term_[0-9a-f]{32}$")
    token: str = Field(default="", max_length=1024)
    folders_only: bool = False
    argv: list[str] | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("token")
    @classmethod
    def _safe_token(cls, value: str) -> str:
        if any(ord(char) < 32 or ord(char) == 127
               or 0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("invalid completion token")
        return value

    @field_validator("argv")
    @classmethod
    def _safe_argv(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if not value[0] or not all(char.isalnum() or char in "_.+-" for char in value[0]):
            raise ValueError("invalid completion command")
        if any(not item or len(item) > 256 or any(
                ord(char) < 32 or ord(char) == 127
                or 0xD800 <= ord(char) <= 0xDFFF for char in item)
               for item in value):
            raise ValueError("invalid completion argv")
        return value


class TerminalCompletionResult(Model):
    directory: str | None = Field(default=None, max_length=4096)
    prefix: str = Field(default="", max_length=1024)
    entries: list[TerminalCompletionEntry] = Field(default_factory=list, max_length=50)
    truncated: bool = False


__all__ = [
    "TerminalCompletionEntry", "TerminalCompletionResult", "TerminalCompletionSpec",
    "TerminalOutputChunk", "TerminalResizeSpec", "TerminalSessionRef",
    "TerminalSpawnSpec",
]

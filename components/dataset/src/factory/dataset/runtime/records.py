"""Canonical conversation record models for dataset generation stages.

Ported from bannff/Agentic-Datasets@26cb683 (``schemas/messages.py``) with
verbatim-in-behavior validators: content strip-nonempty, tool messages
require ``tool_name``, and no consecutive same-role user/assistant messages.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

Role = Literal["system", "user", "assistant", "tool"]


class ToolCall(BaseModel):
    """A tool invocation requested by an assistant message."""

    id: str | None = None
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    # Optional execution info if available
    status: Literal["requested", "completed", "failed"] | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error: str | None = None


class Message(BaseModel):
    """A single conversational message with optional tool interaction."""

    role: Role
    content: str = Field(..., min_length=1)
    metadata: dict[str, Any] | None = None
    # Assistant can request tool calls; tools can return outputs
    tool_calls: list[ToolCall] | None = None
    tool_name: str | None = None  # set when role == "tool"
    tool_call_id: str | None = None  # correlates to assistant's tool_calls[].id
    tool_output: dict[str, Any] | None = None  # structured output from tool

    @field_validator("content")
    @classmethod
    def _strip_content(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("content cannot be empty after stripping")
        return s

    @field_validator("tool_name")
    @classmethod
    def _validate_tool_fields(cls, v: str | None, info: ValidationInfo) -> str | None:
        # If role is 'tool', require tool_name
        role = (info.data or {}).get("role")
        if role == "tool" and not v:
            raise ValueError("tool messages must include tool_name")
        return v


class ConversationRecord(BaseModel):
    """A validated multi-message conversation with provenance metadata."""

    messages: list[Message] = Field(..., min_length=1)
    id: str | None = Field(None, description="Optional unique identifier")
    source: str | None = Field(None, description="Dataset/source provenance")
    metadata: dict[str, Any] | None = None

    @field_validator("messages")
    @classmethod
    def _validate_message_order(cls, v: list[Message]) -> list[Message]:
        # Light check: no two assistants in a row, no two users in a row.
        last_role: Role | None = None
        for m in v:
            if last_role == m.role and m.role in ("user", "assistant"):
                raise ValueError(
                    "Consecutive messages with same conversational role are not allowed"
                )
            last_role = m.role
        return v

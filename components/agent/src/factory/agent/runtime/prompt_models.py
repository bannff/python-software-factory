"""Owner-authored prompt records and template rules.

A prompt is ``name`` + ``description`` + declared ``arguments`` + a ``template``
whose ``{placeholder}`` tokens must each name a declared argument, so a typo is
refused at save time instead of rendering a literal ``{brief}`` into a chat.
Authored prompts live in their own namespace (``origin: authored``), so they can
never shadow a built-in brick prompt.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import TypedToolFailure

_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
NAME_PATTERN = r"^[a-z][a-z0-9_-]{1,63}$"


class PromptArg(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
    description: Annotated[str, Field(max_length=500)] = ""
    required: bool = False


class PromptRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str
    owner_id: str
    prompt_id: Annotated[str, Field(pattern=NAME_PATTERN)]
    description: Annotated[str, Field(max_length=2000)] = ""
    arguments: tuple[PromptArg, ...] = ()
    template: Annotated[str, Field(min_length=1, max_length=20_000)]
    revision: Annotated[int, Field(ge=1)] = 1
    created_at: datetime
    updated_at: datetime


def check_template(template: str, arguments: tuple[PromptArg, ...]) -> None:
    declared = [arg.name for arg in arguments]
    if len(set(declared)) != len(declared):
        raise TypedToolFailure("prompt_invalid", "duplicate argument names")
    unknown = sorted(set(_PLACEHOLDER.findall(template)) - set(declared))
    if unknown:
        raise TypedToolFailure("prompt_invalid", f"undeclared placeholders: {unknown}")


def render(record: PromptRecord, values: dict[str, str]) -> str:
    missing = [a.name for a in record.arguments if a.required and not values.get(a.name)]
    if missing:
        raise TypedToolFailure("prompt_argument_missing", f"missing: {missing}")
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), ""), record.template)


__all__ = ["NAME_PATTERN", "PromptArg", "PromptRecord", "check_template", "render"]

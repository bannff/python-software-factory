"""Immutable transport-neutral catalog records."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class CatalogTool:
    name: str
    description: str
    fn: Callable[..., Any]
    telemetry_excluded_argument_fields: frozenset[str] = frozenset()

    @property
    def tool_name(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class CatalogResource:
    uri: str | None
    uri_template: str | None
    name: str
    description: str
    fn: Callable[..., Any]
    mime_type: str = "text/plain"


@dataclass(frozen=True, slots=True)
class CatalogPromptArgument:
    name: str
    description: str = ""
    required: bool = False


@dataclass(frozen=True, slots=True)
class CatalogPrompt:
    name: str
    description: str
    arguments: tuple[CatalogPromptArgument, ...]
    fn: Callable[..., Any]


@dataclass(frozen=True, slots=True)
class ResourceContent:
    content: str
    mime_type: str = "text/plain"


@dataclass(frozen=True, slots=True)
class ResourceResult:
    contents: tuple[ResourceContent, ...]


@dataclass(frozen=True, slots=True)
class PromptContent:
    text: str


@dataclass(frozen=True, slots=True)
class PromptMessage:
    role: str
    content: PromptContent


@dataclass(frozen=True, slots=True)
class PromptResult:
    messages: tuple[PromptMessage, ...]


__all__ = [
    "CatalogPrompt", "CatalogPromptArgument", "CatalogResource", "CatalogTool",
    "PromptContent", "PromptMessage", "PromptResult", "ResourceContent",
    "ResourceResult",
]

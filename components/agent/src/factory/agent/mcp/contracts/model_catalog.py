"""Strict typed contracts for the Agent safe chat-model catalog tool.

The catalog is deployment-scoped by default (#136): a 450+ row live provider
catalog must never read as 450+ *configured* models, so ``scope="all"`` is an
explicit opt-in and every row carries ``configured`` plus the
``effective_model_id`` it actually resolves to (the pill's single source of
truth). Egress exposes ``model_id``/``provider``/``model`` plus OpenRouter's own
public per-token USD pricing when available (``prompt_usd_per_token``/
``completion_usd_per_token`` — both ``None`` for non-OpenRouter providers, which
have no comparable public pricing source). No endpoint, base URL, credential env
name, secret, or raw catalog error crosses the boundary.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from .discovery import StrictDTO

#: Bound on caller-required selectors; the picker only ever needs the session's
#: own model plus the one it is about to write.
MAX_INCLUDE = 4
MAX_INCLUDE_LENGTH = 256


class ModelCatalogInput(StrictDTO):
    """List the safe chat-model catalog for one deployment scope.

    ``refresh`` bypasses the cached provider catalog and re-fetches live.
    ``scope="all"`` reveals the live provider catalog (marked unconfigured);
    ``include`` names selectors that must be resolvable whatever the scope.
    An out-of-bounds ``include`` is rejected here, never silently dropped.
    """

    refresh: bool = False
    scope: Literal["configured", "all"] = "configured"
    include: list[str] = Field(default_factory=list, max_length=MAX_INCLUDE)

    @field_validator("include")
    @classmethod
    def _bounded_selectors(cls, value: list[str]) -> list[str]:
        for item in value:
            selector = item.strip()
            if not selector:
                raise ValueError("include selectors must be non-empty")
            if len(selector) > MAX_INCLUDE_LENGTH:
                raise ValueError("include selector is too long")
            if any(ord(char) < 32 or ord(char) == 127 for char in selector):
                raise ValueError("include selector must not carry control characters")
        return [item.strip() for item in value]


class ChatModelDTO(StrictDTO):
    """One non-secret model choice suitable for MCP and frontend projection."""

    model_id: str
    provider: str
    model: str
    #: ``provider/model`` — what the selector runs; the pill prints THIS.
    effective_model_id: str
    #: False iff the row came from the live provider catalog, not deployment config.
    configured: bool = True
    prompt_usd_per_token: float | None = None
    completion_usd_per_token: float | None = None


class ModelCatalogOutput(StrictDTO):
    count: int
    models: list[ChatModelDTO]
    #: The scope actually served (a ``..._SCOPE=full`` deployment overrides the argument).
    scope: Literal["configured", "all"] = "configured"
    #: Rows withheld by scoping; the reveal control renders only when > 0.
    hidden_count: int = 0
    #: ``include`` selectors this catalog could not resolve.
    unresolved: list[str] = Field(default_factory=list)


__all__ = [
    "MAX_INCLUDE",
    "MAX_INCLUDE_LENGTH",
    "ChatModelDTO",
    "ModelCatalogInput",
    "ModelCatalogOutput",
]

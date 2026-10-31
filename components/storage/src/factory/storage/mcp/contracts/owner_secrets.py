"""Strict owner-secret MCP contracts (public — list/set/delete, no read).

Identity (tenant_id/principal_id) comes from the ambient envelope, never from
tool input — see mcp/owner_secrets.py. There is deliberately no read/reveal
output model: values are write-only-back, matching upstream's own posture.
"""
from __future__ import annotations

from pydantic import Field

from .base import DTO

_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$"


class OwnerSecretListInput(DTO):
    pass


class OwnerSecretSetInput(DTO):
    name: str = Field(min_length=1, max_length=255, pattern=_NAME_PATTERN)
    value: str = Field(min_length=1, max_length=65536)


class OwnerSecretRefInput(DTO):
    name: str = Field(min_length=1, max_length=255, pattern=_NAME_PATTERN)


class OwnerSecretListOutput(DTO):
    names: list[str]


class OwnerSecretReceiptOutput(DTO):
    name: str
    ok: bool


__all__ = [
    "OwnerSecretListInput", "OwnerSecretListOutput", "OwnerSecretReceiptOutput",
    "OwnerSecretRefInput", "OwnerSecretSetInput",
]

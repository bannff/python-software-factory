"""Strict credential-slot MCP contracts (service-only, caller=auth).

The ``slot`` object is the binding-matched identity + generation coordinate; the
plaintext ``secret`` only ever crosses the in-process service-only boundary to
the auth broker and is never present on any public tool schema. Receipts and
reads carry no secret except the service-only read output.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import DTO, JsonObject

_SLOT_KIND = Literal["client_secret", "refresh_token"]


class SlotRef(DTO):
    """Binding-matched slot coordinate; ``generation`` fences the operation."""
    tenant_id: str = Field(min_length=1, max_length=128)
    owner_id: str = Field(min_length=1, max_length=128)
    provider_id: str = Field(min_length=1, max_length=128)
    connection_ref: str = Field(min_length=1, max_length=128)
    slot_kind: _SLOT_KIND
    generation: int = Field(ge=1)


class CredentialSlotWriteInput(DTO):
    slot: SlotRef
    secret: JsonObject
    expected_version: int | None = Field(default=None, ge=1)


class CredentialSlotRefInput(DTO):
    slot: SlotRef


class CredentialSlotReceiptOutput(DTO):
    generation: int
    version: int


class CredentialSlotReadOutput(DTO):
    """Service-only: decrypted secret returned solely to the auth broker."""
    secret: JsonObject
    generation: int
    version: int

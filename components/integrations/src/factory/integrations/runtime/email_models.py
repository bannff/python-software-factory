"""Provider-neutral email contracts; durable payloads are protected artifacts."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from factory.mcp_utils.interface import ProtectedArtifactRef

_REF = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_KEY = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class StrictEmailModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmailContent(StrictEmailModel):
    """Validated plaintext only while a provider call is in progress."""
    recipients: list[str] = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1, max_length=65_536)

    @field_validator("recipients")
    @classmethod
    def _recipients(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values) or not all(_EMAIL.fullmatch(v) for v in values):
            raise ValueError("recipients must be unique email addresses")
        return values


class SendEmailRequest(EmailContent):
    """Internal provider request, never an MCP or Workflow payload."""
    connection_ref: str = Field(min_length=8, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)

    @field_validator("connection_ref")
    @classmethod
    def _opaque_reference(cls, value: str) -> str:
        if not _REF.fullmatch(value): raise ValueError("connection_ref must be opaque")
        return value

    @field_validator("idempotency_key")
    @classmethod
    def _key(cls, value: str) -> str:
        if not _KEY.fullmatch(value): raise ValueError("invalid idempotency_key")
        return value

    def intent_digest(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(exclude={"idempotency_key"}), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class SendProtectedEmailRequest(StrictEmailModel):
    """Public artifact-reference-only request; no email content crosses the wire."""
    connection_ref: str = Field(min_length=8, max_length=128)
    artifact: ProtectedArtifactRef
    idempotency_key: str = Field(min_length=1, max_length=128)

    @field_validator("connection_ref")
    @classmethod
    def _opaque_reference(cls, value: str) -> str:
        if not _REF.fullmatch(value): raise ValueError("connection_ref must be opaque")
        return value

    @field_validator("idempotency_key")
    @classmethod
    def _key(cls, value: str) -> str:
        if not _KEY.fullmatch(value): raise ValueError("invalid idempotency_key")
        return value


class EmailReceipt(StrictEmailModel):
    status: Literal["sent"]
    message_id: str = Field(min_length=1, max_length=256)
    intent_digest: str = Field(min_length=64, max_length=64)

    @field_validator("intent_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        if not _DIGEST.fullmatch(value): raise ValueError("invalid intent_digest")
        return value


class EmailIdempotencyConflict(StrictEmailModel):
    status: Literal["idempotency_conflict"]


class ProviderReceiptError(ValueError):
    """A provider receipt could not be safely projected to callers."""

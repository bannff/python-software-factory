"""Immutable, locally verifiable source/evidence records for failure patterns."""
from __future__ import annotations

from datetime import datetime
import hashlib
import re
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator

from .scenario_pack_models import FrozenModel, digest, text, token


class FailurePatternSource(FrozenModel):
    source_id: str
    source_url: str
    spdx_license: str
    version: str
    retrieved_at: str
    retrieved_content: str
    source_digest: str

    @field_validator("source_id", "spdx_license", "version")
    @classmethod
    def _tokens(cls, value: str) -> str:
        return token(value, "failure source identity")

    @field_validator("source_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "failure source")

    @model_validator(mode="after")
    def _immutable_metadata(self) -> "FailurePatternSource":
        parsed = urlparse(self.source_url)
        if parsed.scheme != "https":
            raise ValueError("failure source URL must use HTTPS")
        if not re.search(r"/[0-9a-fA-F]{40}(?:/|$)", parsed.path):
            raise ValueError("failure source URL must contain an immutable content version")
        text(self.retrieved_content, "failure source retrieved content")
        if hashlib.sha256(self.retrieved_content.encode()).hexdigest() != self.source_digest:
            raise ValueError("failure source digest does not match retrieved content")
        try:
            datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("failure source retrieved_at must be ISO-8601") from error
        return self


class FailurePatternEvidence(FrozenModel):
    evidence_id: str
    source_id: str
    locator: str
    range_start: int = Field(strict=True, ge=0)
    range_end: int = Field(strict=True, gt=0)

    @field_validator("evidence_id", "source_id")
    @classmethod
    def _tokens(cls, value: str) -> str:
        return token(value, "failure evidence identity")

    @field_validator("locator")
    @classmethod
    def _text(cls, value: str) -> str:
        return text(value, "failure evidence locator")

    @model_validator(mode="after")
    def _range(self) -> "FailurePatternEvidence":
        if self.range_end <= self.range_start:
            raise ValueError("failure evidence range must be ordered")
        return self


__all__ = ["FailurePatternEvidence", "FailurePatternSource"]

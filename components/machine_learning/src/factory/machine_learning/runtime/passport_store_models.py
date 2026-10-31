"""Typed references and failures for ModelPassport registries."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from .passport_refs import FrozenModel
from .passport_validation import require_digest, require_text, require_uri


class ModelPassportRef(FrozenModel):
    model_id: str
    model_version: str
    passport_revision: int = Field(strict=True, gt=0)
    uri: str
    digest: str

    @field_validator("model_id", "model_version")
    @classmethod
    def _identity(cls, value: str) -> str:
        return require_text(value, "passport reference identity/version")

    @field_validator("uri")
    @classmethod
    def _uri(cls, value: str) -> str:
        return require_uri(value, "passport reference URI")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return require_digest(value, "passport reference digest")


class ModelPassportPublication(FrozenModel):
    status: Literal["published", "existing"]
    ref: ModelPassportRef


class ModelPassportConflictError(ValueError):
    """A logical model/version/revision key already has different content."""


class ModelPassportIntegrityError(ValueError):
    """Stored passport bytes, reference, or path failed integrity checks."""


class ModelPassportRevisionError(ValueError):
    """Publication would create a revision gap or invalid predecessor link."""


__all__ = [
    "ModelPassportConflictError", "ModelPassportIntegrityError",
    "ModelPassportPublication", "ModelPassportRef", "ModelPassportRevisionError",
]

"""Domain-neutral contracts for immutable definition artifacts."""
from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, JsonValue, field_validator, model_validator

from .scenario_pack_models import FrozenModel, digest, text, token


class DefinitionArtifact(FrozenModel):
    """Data-only, versioned definition whose full canonical bytes are sealed."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_name: str
    schema_version: str
    identity: str
    version: str
    content: dict[str, JsonValue]

    @field_validator("schema_name", "schema_version", "identity", "version")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "definition schema/identity/version")


class DefinitionArtifactRef(FrozenModel):
    schema_name: str
    schema_version: str
    identity: str
    version: str
    uri: str
    digest: str
    size_bytes: int = Field(strict=True, gt=0)

    @field_validator("schema_name", "schema_version", "identity", "version")
    @classmethod
    def _token(cls, value: str) -> str:
        return token(value, "definition reference schema/identity/version")

    @field_validator("uri")
    @classmethod
    def _uri(cls, value: str) -> str:
        return text(value, "definition reference URI")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "definition artifact")


class DefinitionArtifactConflict(FrozenModel):
    identity: str
    version: str
    existing_digest: str
    requested_digest: str
    reason: str = "definition identity/version already has different content"


class DefinitionArtifactPublishResult(FrozenModel):
    status: Literal["published", "existing", "conflict"]
    ref: DefinitionArtifactRef | None = None
    conflict: DefinitionArtifactConflict | None = None

    @model_validator(mode="after")
    def _shape(self) -> "DefinitionArtifactPublishResult":
        if (self.status == "conflict") != (self.conflict is not None):
            raise ValueError("definition publish conflict shape is invalid")
        if (self.status != "conflict") != (self.ref is not None):
            raise ValueError("definition publish reference shape is invalid")
        return self


class DefinitionArtifactIntegrityError(ValueError):
    """Raised when a definition reference or its immutable bytes fail closed."""


__all__ = [
    "DefinitionArtifact", "DefinitionArtifactConflict",
    "DefinitionArtifactIntegrityError", "DefinitionArtifactPublishResult",
    "DefinitionArtifactRef",
]

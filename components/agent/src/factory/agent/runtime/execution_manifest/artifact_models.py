"""Dataset-compatible immutable DefinitionArtifact contracts."""
from __future__ import annotations

from pydantic import Field, JsonValue, model_validator

from .base import FrozenModel


class DefinitionArtifact(FrozenModel):
    schema_name: str
    schema_version: str
    identity: str
    version: str
    content: dict[str, JsonValue]


class DefinitionArtifactRef(FrozenModel):
    schema_name: str
    schema_version: str
    identity: str
    version: str
    uri: str
    digest: str
    size_bytes: int = Field(gt=0)


class DefinitionDescriptor(FrozenModel):
    inline: DefinitionArtifact | None = None
    reference: DefinitionArtifactRef | None = None

    @model_validator(mode="after")
    def _exclusive(self) -> "DefinitionDescriptor":
        if (self.inline is None) == (self.reference is None):
            raise ValueError("exactly one of inline or reference is required")
        return self


__all__ = ["DefinitionArtifact", "DefinitionArtifactRef", "DefinitionDescriptor"]

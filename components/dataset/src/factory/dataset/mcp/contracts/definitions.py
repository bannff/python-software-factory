"""Strict flat MCP contracts for immutable definition artifacts."""
from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field, JsonValue, StrictInt, StrictStr

from .base import InputDTO, OutputDTO


class PublishDefinitionArtifactInput(InputDTO):
    artifact_json: StrictStr


class ResolveDefinitionArtifactInput(InputDTO):
    preserve_domain_schema_version: ClassVar[bool] = True
    schema_name: StrictStr
    schema_version: StrictStr
    identity: StrictStr
    version: StrictStr
    uri: StrictStr
    digest: StrictStr
    size_bytes: StrictInt = Field(gt=0)


class DefinitionArtifactRefOutput(OutputDTO):
    schema_name: StrictStr
    schema_version: StrictStr
    identity: StrictStr
    version: StrictStr
    uri: StrictStr
    digest: StrictStr
    size_bytes: StrictInt


class DefinitionArtifactConflictOutput(OutputDTO):
    identity: StrictStr
    version: StrictStr
    existing_digest: StrictStr
    requested_digest: StrictStr
    reason: StrictStr


class PublishDefinitionArtifactOutput(OutputDTO):
    status: Literal["published", "existing", "conflict"]
    ref: DefinitionArtifactRefOutput | None = None
    conflict: DefinitionArtifactConflictOutput | None = None


class ResolveDefinitionArtifactOutput(OutputDTO):
    schema_name: StrictStr
    schema_version: StrictStr
    identity: StrictStr
    version: StrictStr
    content: dict[StrictStr, JsonValue]


__all__ = [name for name in globals() if name.endswith(("Input", "Output"))]

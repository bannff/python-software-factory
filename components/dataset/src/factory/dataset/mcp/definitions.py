"""Typed MCP publication and resolution for immutable definitions."""
from __future__ import annotations

from pathlib import Path

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, operational

from .contracts.definitions import (
    PublishDefinitionArtifactInput, PublishDefinitionArtifactOutput,
    ResolveDefinitionArtifactInput, ResolveDefinitionArtifactOutput,
)
from ..interface import (
    dataset_publish_definition_artifact, dataset_resolve_definition_artifact,
)
from ..runtime.definition_codec import parse_definition_json
from ..runtime.definition_models import DefinitionArtifactRef


def register(
    mcp: Any, storage_root: Path | None, max_size_bytes: int,
) -> None:
    """Register definition tools against the server-configured storage root."""

    @mcp.tool(name="dataset_publish_definition_artifact")
    @operational(
        input_model=PublishDefinitionArtifactInput,
        output_model=PublishDefinitionArtifactOutput,
    )
    def publish_definition_artifact(
        artifact_json: str,
    ) -> ToolResult[PublishDefinitionArtifactOutput]:
        """Publish JSON definition data under the configured Dataset root."""
        artifact = parse_definition_json(artifact_json, max_size_bytes)
        result = dataset_publish_definition_artifact(
            artifact, storage_root, max_size_bytes,
        )
        return result.model_dump(mode="json")

    @mcp.tool(name="dataset_resolve_definition_artifact")
    @deterministic(
        input_model=ResolveDefinitionArtifactInput,
        output_model=ResolveDefinitionArtifactOutput,
    )
    def resolve_definition_artifact(
        schema_name: str, schema_version: str, identity: str, version: str,
        uri: str, digest: str, size_bytes: int,
    ) -> ToolResult[ResolveDefinitionArtifactOutput]:
        """Resolve a reference under the configured root with full verification."""
        artifact = dataset_resolve_definition_artifact(
            DefinitionArtifactRef(
                schema_name=schema_name, schema_version=schema_version,
                identity=identity, version=version, uri=uri, digest=digest,
                size_bytes=size_bytes,
            ),
            storage_root, max_size_bytes,
        )
        return artifact.model_dump(mode="json")


__all__ = ["register"]

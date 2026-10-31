"""Strict protected-artifact MCP contracts."""
from __future__ import annotations

from typing import Literal

from factory.mcp_utils.interface import (
    ProtectedArtifactRef, ProtectedContentDescriptor, ProtectedContentProjection,
)

from .base import DTO, JsonObject


class ProtectedArtifactCreateInput(DTO):
    descriptor: ProtectedContentDescriptor
    content: JsonObject


class ProtectedArtifactCreateOutput(DTO):
    status: Literal["created", "matched"]
    artifact: ProtectedArtifactRef


class ProtectedArtifactRefInput(DTO):
    artifact: ProtectedArtifactRef


class ProtectedArtifactProjectOutput(DTO):
    projection: ProtectedContentProjection


class ProtectedArtifactTombstoneOutput(DTO):
    tombstoned: bool


class ProtectedArtifactMaterializeOutput(DTO):
    content: JsonObject

"""Strict MCP ingress for trusted relationship projection."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..runtime.projection_reconcile import ReconcileRecord
from ..runtime.relationship_projection import ProjectionModel, ProjectionRecord


class ProjectEventInput(ProjectionModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    owner_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["graph.projection.requested"]
    subject_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=0)
    payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    record: ProjectionRecord
    backend: str = ""



class ReconcileProjectionInput(ProjectionModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    owner_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["graph.projection.reconcile"]
    subject_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=0)
    payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_system: str = Field(min_length=1, max_length=64)
    snapshot_id: str = Field(min_length=1, max_length=128)
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    ordinal_start: int = Field(ge=0)
    cursor: str | None = Field(default=None, max_length=256)
    next_cursor: str | None = Field(default=None, max_length=256)
    records: list[ReconcileRecord] = Field(min_length=1, max_length=256)
    backend: str = ""

__all__ = ["ProjectEventInput", "ReconcileProjectionInput"]

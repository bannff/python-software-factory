"""Immutable authority binding for human-gated Dataset materialization."""
from __future__ import annotations

from pydantic import field_validator

from .blueprint_models import DatasetHumanApprovalRef, DatasetQualityPolicyRef
from .scenario_pack_models import FrozenModel, digest


class DatasetApprovalBinding(FrozenModel):
    """Exact approval authority persisted from submission through manifest."""

    approval: DatasetHumanApprovalRef
    blueprint_digest: str
    quality_policy: DatasetQualityPolicyRef

    @field_validator("blueprint_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "approved blueprint")

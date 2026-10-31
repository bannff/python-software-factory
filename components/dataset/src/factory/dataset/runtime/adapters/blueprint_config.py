"""Config-backed seams for opaque Evals policy and human approval references."""
from __future__ import annotations

import json
import os

from pydantic import TypeAdapter

from ..blueprint_codec import approval_digest
from ..blueprint_models import (
    DatasetHumanApprovalRecord, DatasetHumanApprovalRef, DatasetQualityPolicyRef,
)


class ConfiguredQualityPolicyRegistry:
    def __init__(self, refs: tuple[DatasetQualityPolicyRef, ...] = ()) -> None:
        self._refs = {(item.id, item.revision): item for item in refs}
        if len(self._refs) != len(refs):
            raise ValueError("Duplicate Evals quality-policy reference")

    @classmethod
    def from_environment(cls) -> "ConfiguredQualityPolicyRegistry":
        raw = os.environ.get("DATASET_QUALITY_POLICY_REFS_JSON", "[]")
        refs = TypeAdapter(tuple[DatasetQualityPolicyRef, ...]).validate_python(json.loads(raw))
        return cls(refs)

    def require(self, ref: DatasetQualityPolicyRef) -> None:
        if self._refs.get((ref.id, ref.revision)) != ref:
            raise ValueError("Unknown or mismatched Evals quality-policy reference")


class ConfiguredHumanApprovalRegistry:
    def __init__(self, records: tuple[DatasetHumanApprovalRecord, ...] = ()) -> None:
        self._records = {(item.id, item.revision): item for item in records}
        if len(self._records) != len(records):
            raise ValueError("Duplicate human approval reference")

    @classmethod
    def from_environment(cls) -> "ConfiguredHumanApprovalRegistry":
        raw = os.environ.get("DATASET_HUMAN_APPROVALS_JSON", "[]")
        records = TypeAdapter(tuple[DatasetHumanApprovalRecord, ...]).validate_python(
            json.loads(raw)
        )
        return cls(records)

    def require(
        self, ref: DatasetHumanApprovalRef, blueprint_digest: str,
        quality_policy: DatasetQualityPolicyRef,
    ) -> None:
        record = self._records.get((ref.id, ref.revision))
        if record is None or approval_digest(record) != ref.digest:
            raise ValueError("Unknown or mismatched human approval reference")
        if record.blueprint_digest != blueprint_digest:
            raise ValueError("Human approval is not bound to this blueprint digest")
        if record.quality_policy != quality_policy:
            raise ValueError("Human approval is not bound to this quality-policy reference")

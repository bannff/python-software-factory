"""Canonical encoding and digest helpers for DatasetBlueprint contracts."""
from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel

from .blueprint_models import (
    DatasetBlueprint, DatasetBlueprintBinding, DatasetBlueprintLineage,
    DatasetHumanApprovalRecord,
)


def canonical_json(value: BaseModel | dict | list | tuple) -> bytes:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest(value: BaseModel | dict | list | tuple) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def blueprint_binding(blueprint: DatasetBlueprint) -> DatasetBlueprintBinding:
    return DatasetBlueprintBinding(
        identity=blueprint.identity,
        version=blueprint.version,
        digest=canonical_digest(blueprint),
        quality_policy=blueprint.quality_policy,
    )


def blueprint_lineage(
    blueprint: DatasetBlueprint, binding: DatasetBlueprintBinding,
) -> DatasetBlueprintLineage:
    return DatasetBlueprintLineage(
        binding=binding, recipe=blueprint.recipe, stages=blueprint.stages,
        output_schema=blueprint.output_schema,
        source_evidence=blueprint.source_evidence,
        capabilities=blueprint.capabilities,
    )


def approval_digest(record: DatasetHumanApprovalRecord) -> str:
    return canonical_digest(record)

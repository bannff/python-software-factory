"""Closed reconstruction of manifest-bound structured output types."""
from __future__ import annotations

from typing import Any

from .canonical import canonical_bytes, sha256
from .descriptors import OutputSchemaDescriptor


def build_output_schema(descriptor: OutputSchemaDescriptor | None) -> type[Any] | None:
    if descriptor is None:
        return None
    from factory.agent.runtime.graph_output_models import (
        ResearchDraft, ResearchEvidence, ResearchPlan,
    )

    schemas = {
        "research-plan-v1": ResearchPlan,
        "research-evidence-v1": ResearchEvidence,
        "research-draft-v1": ResearchDraft,
    }
    try:
        model = schemas[descriptor.name]
    except KeyError as exc:
        raise ValueError(f"unknown manifest output schema: {descriptor.name!r}") from exc
    actual = model.model_json_schema()
    if descriptor.digest != sha256(canonical_bytes(actual)) or actual != descriptor.json_schema:
        raise ValueError("manifest output schema does not match closed assembler schema")
    return model


__all__ = ["build_output_schema"]

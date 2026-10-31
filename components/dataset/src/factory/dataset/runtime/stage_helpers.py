"""Checkpoint and scenario helpers for recipe stage execution."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import (
    DatasetFallbackRecord, DatasetGenerationRequest, DatasetStageCheckpoint,
)
from .helpers import _sha256
from .scenario_errors import ScenarioGenerationError
from .scenario_models import ScenarioPackGenerationInput, ScenarioPackLineage
from .validation import dispatch_validator


def _validate_scenario_stage(
    stage,
    records: list[Any],
    lineage: ScenarioPackLineage | None,
    expected: ScenarioPackGenerationInput,
) -> None:
    if lineage is None or (
        lineage.scenario_pack != expected.scenario_pack
        or lineage.generator_adapter != expected.generator_adapter
        or lineage.generator_version != expected.generator_version
        or lineage.seed != expected.seed
    ):
        raise ScenarioGenerationError(
            "Scenario stage lineage does not match the submitted request"
        )
    validator = getattr(stage, "validate_lineage", None)
    if not callable(validator):
        raise ScenarioGenerationError(
            "scenario_generate stage must validate canonical lineage"
        )
    validator(records, lineage)
def _extract_scenario_lineage(stage) -> ScenarioPackLineage | None:
    value = getattr(stage, "scenario_lineage", None)
    if value is None or isinstance(value, ScenarioPackLineage):
        return value
    return ScenarioPackLineage.model_validate(value)
def _extract_fallback(stage, request: DatasetGenerationRequest) -> DatasetFallbackRecord | None:
    fallback = getattr(stage, "fallback_record", None)
    if fallback is None:
        return None
    if not isinstance(fallback, DatasetFallbackRecord):
        fallback = DatasetFallbackRecord.model_validate(fallback)
    require_authorized_fallback(request, fallback)
    return fallback
def require_authorized_fallback(
    request: DatasetGenerationRequest, fallback: DatasetFallbackRecord,
) -> None:
    if not fallback.authorized:
        raise ValueError("Stage fallback must be explicitly authorized")
    if fallback.actual_backend not in request.execution_policy.allowed_fallbacks:
        raise ValueError("Stage fallback backend is not allowed by policy")
def _load_checkpoint_records(
    checkpoint: DatasetStageCheckpoint,
    record_schema: str,
    checkpoint_root: Path,
    job_id: str,
    *,
    require_digest: bool,
    allowed_local_roots: tuple[Path, ...] = (),
) -> list[Any]:
    from .checkpoint_integrity import (
        checked_output_path,
        validate_checkpoint_metadata,
    )
    output_path = checked_output_path(checkpoint, checkpoint_root, record_schema)
    from .atomic_io import read_bytes_no_follow
    try:
        content = read_bytes_no_follow(output_path)
    except OSError:
        raise ValueError("Stage checkpoint output is missing") from None
    if _sha256(content) != checkpoint.output_digest:
        raise ValueError("Stage checkpoint output digest does not match")
    records = [json.loads(content)] if record_schema == "can_artifact" else [
        json.loads(line) for line in content.decode().splitlines() if line.strip()
    ]
    validated = list(dispatch_validator(records, record_schema=record_schema))
    validate_checkpoint_metadata(
        checkpoint, validated, job_id=job_id, require_digest=require_digest,
        record_schema=record_schema, allowed_local_roots=allowed_local_roots,
    )
    return validated

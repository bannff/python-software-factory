"""Immutable local stage checkpoint storage."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from ..checkpoint_integrity import (
    checkpoint_metadata_digest,
    local_roots_policy_digest,
)
from ..contracts import (
    DatasetFallbackRecord,
    DatasetProvenanceRecord,
    DatasetQualityResults,
    DatasetStageCheckpoint,
)
from ..scenario_models import ScenarioPackLineage


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class LocalStageCheckpointStore:
    """Write-once stage outputs and reproducibility metadata."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self, *, stage_name: str, stage_index: int, input_digest: str,
        records: list[Any], schema_version: str, adapter_version: str,
        config: dict[str, Any] | None = None, context_snapshot_digest: str,
        tool_schema_snapshot_digest: str, provenance: DatasetProvenanceRecord,
        quality_results: DatasetQualityResults,
        fallback: DatasetFallbackRecord | None = None,
        record_schema: Literal[
            "conversation", "can_frame", "can_artifact", "generic",
            "edge_sensor_window",
        ] = "conversation",
        scenario_lineage: ScenarioPackLineage | None = None,
        allowed_local_roots: tuple[Path, ...] = (),
    ) -> DatasetStageCheckpoint:
        """Validate and atomically persist one immutable stage result."""
        from ..validation import dispatch_validator
        validated = list(dispatch_validator(records, record_schema=record_schema))
        if record_schema == "conversation":
            output_content = b"".join(
                (json.dumps(item.model_dump(mode="json"), sort_keys=True) + "\n").encode()
                for item in validated
            )
        elif record_schema == "can_artifact":
            if len(validated) != 1 or not isinstance(validated[0], dict):
                raise ValueError("CAN artifact stages must emit exactly one object")
            output_content = json.dumps(
                validated[0], sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            ).encode()
        else:
            output_content = b"".join(
                (json.dumps(
                    item.model_dump(mode="json")
                    if hasattr(item, "model_dump") else item,
                    sort_keys=True,
                ) + "\n").encode()
                for item in validated
            )
        output_digest = _sha256(output_content)
        config_content = json.dumps(
            config or {}, sort_keys=True, separators=(",", ":")
        ).encode()
        suffix = ".json" if record_schema == "can_artifact" else ".jsonl"
        output_path = self.root / f"stage-{stage_index}-{output_digest}{suffix}"
        checkpoint_path = self.root / f"stage-{stage_index}-{output_digest}.checkpoint.json"
        _write_once(output_path, output_content)
        checkpoint = DatasetStageCheckpoint(
            stage_name=stage_name, stage_index=stage_index, input_digest=input_digest,
            output_uri=output_path.resolve().as_uri(), output_digest=output_digest,
            record_count=len(validated), schema_version=schema_version,
            adapter_version=adapter_version, config_digest=_sha256(config_content),
            context_snapshot_digest=context_snapshot_digest,
            tool_schema_snapshot_digest=tool_schema_snapshot_digest,
            provenance=provenance, quality_results=quality_results,
            allowed_local_roots_digest=(
                local_roots_policy_digest(allowed_local_roots)
                if record_schema == "edge_sensor_window" else None
            ),
            scenario_lineage=scenario_lineage, fallback=fallback,
            created_at=datetime.now(UTC),
        )
        checkpoint = checkpoint.model_copy(update={
            "checkpoint_digest": checkpoint_metadata_digest(checkpoint),
        })
        _write_once(
            checkpoint_path, checkpoint.model_dump_json(exclude_none=True).encode(),
        )
        return checkpoint


def _write_once(path: Path, content: bytes) -> None:
    from ..atomic_io import atomic_write_immutable
    atomic_write_immutable(path, content)

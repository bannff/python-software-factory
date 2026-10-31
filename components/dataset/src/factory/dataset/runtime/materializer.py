"""Recipe materializer for immutable dataset views."""
from __future__ import annotations

import json
from pathlib import Path

from .adapters.checkpoints import LocalStageCheckpointStore
from .bundle_writer import write_bundle
from .contracts import DatasetArtifactRef, DatasetJobStatus, DatasetStageCheckpoint
from .helpers import _verify_snapshot_ref
from .ports import DatasetStagePort
from .recipe import load_records, resolve_recipe
from .stage_registry import default_stages
from .stage_runner import run_stage_loop


class LocalDatasetMaterializer:
    """Resolve recipes, execute stages, and materialize immutable dataset views."""

    def __init__(self, store, stages: dict[str, DatasetStagePort] | None = None) -> None:
        self.store = store
        self.stages = stages or default_stages(store.root)

    @property
    def root(self) -> Path:
        return self.store.root

    def materialize(self, status: DatasetJobStatus) -> DatasetArtifactRef:
        request = status.request
        from .blueprint_validation import require_submission_authority
        require_submission_authority(request, self.store.root)
        recipe = resolve_recipe(request)
        self._require_job_running(status.job_id)
        if not request.execution_policy.fail_closed:
            raise ValueError("Dataset execution policy must be fail-closed")
        if not request.execution_policy.retry_from_checkpoint_only:
            raise ValueError(
                "Dataset execution policy must retry from immutable checkpoints only"
            )
        _verify_snapshot_ref(request.context_snapshot, label="Context")
        self._write_resolved_context(request, recipe, status.job_id)
        _verify_snapshot_ref(request.tool_schema_snapshot, label="Tool schema")
        records = [] if recipe.record_schema == "can_frame" else load_records(
            request, record_schema=recipe.record_schema,
        )
        checkpoints = LocalStageCheckpointStore(
            self.store.root / "checkpoints" / status.job_id
        )
        existing = self._load_stage_checkpoints(status.job_id)
        records, versions, provenance, quality, fallback, lineage = run_stage_loop(
            recipe, request, records, self.stages, checkpoints, existing, status.job_id,
            check_running=lambda: self._require_job_running(status.job_id),
        )
        if not records:
            raise ValueError(
                "Dataset materialization produced zero records; final publication aborted"
            )
        if request.scenario_generation is not None and not quality.passed:
            raise ValueError("Scenario generation failed final quality validation")
        if recipe.record_schema == "edge_sensor_window" and not quality.passed:
            raise ValueError("Edge sensor dataset failed split leakage validation")
        if recipe.record_schema == "edge_routing_example" and not quality.passed:
            raise ValueError("Edge routing dataset failed quality validation")
        self._require_job_running(status.job_id)
        return write_bundle(
            self.store, records, request, recipe, status.job_id,
            versions, lineage, quality, provenance, fallback,
        )

    def _require_job_running(self, job_id: str) -> DatasetJobStatus:
        current = self.store.get_job(job_id)
        if current is None:
            raise ValueError(f"Unknown dataset job: {job_id}")
        if current.status != "running":
            raise RuntimeError(f"Dataset job is not running: {job_id}")
        return current

    def _write_resolved_context(self, request, recipe, job_id: str) -> None:
        """Best-effort write of resolved recipe config to a per-job audit file."""
        from .recipe import path_from_uri
        try:
            snapshot_path = path_from_uri(request.context_snapshot.uri)
            audit_path = snapshot_path.with_name(f"context-resolved-{job_id}.json")
            merged_config: dict = {}
            for stage in recipe.stages:
                merged_config.update(stage.config)
            context_data = {
                "recipe_uri": request.recipe_uri,
                "recipe_digest": request.recipe_digest,
                "resolved_config": {
                    "failure_rate": merged_config.get("failure_rate", 0.1),
                    "failure_modes": merged_config.get("failure_modes", []),
                    "multiplier": merged_config.get("multiplier", 10),
                    "seed": merged_config.get("seed", 42),
                    "method": merged_config.get("method", "gaussian_copula"),
                },
                "input_artifacts": [item.uri for item in request.input_artifacts],
                "execution_policy": {
                    "fail_closed": request.execution_policy.fail_closed,
                    "retry_from_checkpoint_only": (
                        request.execution_policy.retry_from_checkpoint_only
                    ),
                },
            }
            from .atomic_io import atomic_write
            atomic_write(audit_path, json.dumps(
                context_data, sort_keys=True, indent=2,
            ).encode())
        except (OSError, TypeError, ValueError):
            return

    def _load_stage_checkpoints(self, job_id: str) -> dict[int, DatasetStageCheckpoint]:
        checkpoint_root = self.store.root / "checkpoints" / job_id
        if not checkpoint_root.exists():
            return {}
        checkpoints: dict[int, DatasetStageCheckpoint] = {}
        from .atomic_io import read_bytes_no_follow
        for path in sorted(checkpoint_root.glob("stage-*.checkpoint.json")):
            checkpoint = DatasetStageCheckpoint.model_validate_json(
                read_bytes_no_follow(path)
            )
            if checkpoint.stage_index in checkpoints and checkpoints[checkpoint.stage_index] != checkpoint:
                raise ValueError("Duplicate stage checkpoint detected")
            checkpoints[checkpoint.stage_index] = checkpoint
        return checkpoints

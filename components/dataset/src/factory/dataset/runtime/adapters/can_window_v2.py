"""Ref-only v2 CAN window stage backed by Dataset-issued artifacts."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from typing import Any

from pydantic import TypeAdapter

from .can_window import _positive, _windows
from .can_window_builder import _timestamp
from ..can_artifact_codec import load_prior_policy, load_signal_schema
from ..can_artifact_models import CanArtifactRef

_REF_MAP = TypeAdapter(dict[str, CanArtifactRef])


class CanWindowV2StageAdapter:
    """Emit exact v2 planes; discovery and inline authorization are forbidden."""

    name = "can_window_v2"
    stage_version = "factory-can-window-2"
    allowed_config = frozenset({
        "window_size_ms", "step_size_ms", "grid_resolution_ms", "input_uri",
        "emit_timespans", "observation_cutoff_ms", "label_horizon_ms",
        "prior_data_policy_ref", "signal_schema_refs_by_can_id",
    })

    def execute(
        self, records: Iterable[Any], config: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        values = dict(config or {})
        unknown = set(values) - self.allowed_config
        if unknown:
            raise ValueError(f"Unsupported can_window_v2 configuration: {sorted(unknown)}")
        if "prior_data_policy_ref" not in values:
            raise ValueError("can_window_v2 requires prior_data_policy_ref")
        if "signal_schema_refs_by_can_id" not in values:
            raise ValueError("can_window_v2 requires signal_schema_refs_by_can_id")
        policy_ref = CanArtifactRef.model_validate(values["prior_data_policy_ref"])
        signal_refs = _REF_MAP.validate_python(values["signal_schema_refs_by_can_id"])
        if not signal_refs:
            raise ValueError("signal_schema_refs_by_can_id must be non-empty")
        policy = load_prior_policy(policy_ref)
        schemas = {can_id: load_signal_schema(ref) for can_id, ref in signal_refs.items()}
        for can_id, schema in schemas.items():
            if schema.can_id != can_id:
                raise ValueError("signal schema map key disagrees with artifact CAN-ID")
        window_ms = _positive(values, "window_size_ms", 5000)
        step_ms = _positive(values, "step_size_ms", window_ms)
        grid_ms = _positive(values, "grid_resolution_ms", 10)
        cutoff_ms = _positive(values, "observation_cutoff_ms", window_ms)
        horizon_ms = values.get("label_horizon_ms", 0)
        if isinstance(horizon_ms, bool) or not isinstance(horizon_ms, int) or horizon_ms < 0:
            raise ValueError("label_horizon_ms must be a non-negative integer")
        if cutoff_ms % grid_ms:
            raise ValueError("observation_cutoff_ms must be divisible by grid_resolution_ms")
        items = list(records)
        if not items and values.get("input_uri"):
            input_uri = str(values["input_uri"])
            from .can_input_guard import guard_standalone_can_input
            from ..helpers import load_records_from_uri
            guard_standalone_can_input(input_uri)
            items = load_records_from_uri(input_uri)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            if item.get("decoded_signals"):
                grouped[str(item["arbitration_id"])].append(item)
        missing = sorted(set(grouped) - set(schemas))
        if missing:
            raise ValueError(f"signal schema refs missing CAN-IDs: {missing}")
        for can_id, group in sorted(grouped.items()):
            group.sort(key=_timestamp)
            metadata = {
                "signal_schema_ref": signal_refs[can_id].model_dump(mode="json"),
                "prior_data_policy_ref": policy_ref.model_dump(mode="json"),
            }
            yield from _windows(
                group, can_id=can_id,
                signal_columns=list(schemas[can_id].signal_columns),
                context_columns=list(policy.prior_data_allowlist), context_policy=None,
                window_ms=window_ms, step_ms=step_ms, grid_ms=grid_ms,
                cutoff_ms=cutoff_ms, horizon_ms=horizon_ms,
                emit_timespans=bool(values.get("emit_timespans", False)),
                exact_v2=True, metadata=metadata,
            )


__all__ = ["CanWindowV2StageAdapter"]

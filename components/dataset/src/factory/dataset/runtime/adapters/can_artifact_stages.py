"""Dataset stages that issue exact CAN policy and per-CAN schema artifacts."""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from ..can_artifact_codec import create_prior_policy, create_signal_schema
from ..helpers import load_records_from_uri

PRIOR_NUMERIC_FIELDS = frozenset({
    "aggressiveness_score", "battery_health_pct", "humidity_pct", "lat", "lon",
    "odometer_km", "precipitation_mm", "temp_c",
})


class CanPriorPolicyStageAdapter:
    name = "can_prior_policy"
    stage_version = "factory-can-prior-policy-1"
    allowed_config = frozenset({
        "use_context", "prior_data_allowlist", "source_digests",
    })

    def execute(
        self, records: Iterable[Any], config: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        for _ in records:
            pass
        values = dict(config or {})
        _reject_unknown(values, self.allowed_config, self.name)
        use_context = values.get("use_context", False)
        if not isinstance(use_context, bool):
            raise ValueError("use_context must be boolean")
        requested = values.get("prior_data_allowlist") or []
        if not isinstance(requested, list) or any(
            not isinstance(item, str) for item in requested
        ):
            raise ValueError("prior_data_allowlist must be a string list")
        if len(set(requested)) != len(requested):
            raise ValueError("prior_data_allowlist entries must be unique")
        rejected = sorted(set(requested) - PRIOR_NUMERIC_FIELDS)
        if rejected:
            raise ValueError(f"context columns are not approved prior numeric data: {rejected}")
        if bool(requested) != use_context:
            raise ValueError("use_context and prior_data_allowlist disagree")
        yield create_prior_policy(
            use_context=use_context,
            prior_data_allowlist=tuple(requested),
            source_digests=values.get("source_digests") or (),
        ).model_dump(mode="json")


class CanSignalSchemaStageAdapter:
    name = "can_signal_schema"
    stage_version = "factory-can-signal-schema-1"
    allowed_config = frozenset({"input_uri", "can_id", "source_digests"})

    def execute(
        self, records: Iterable[Any], config: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        values = dict(config or {})
        _reject_unknown(values, self.allowed_config, self.name)
        can_id = values.get("can_id")
        if not isinstance(can_id, str) or not can_id:
            raise ValueError("signal schema requires a non-empty can_id")
        items = list(records)
        if not items and values.get("input_uri"):
            items = load_records_from_uri(str(values["input_uri"]))
        if len(items) != 1 or str(items[0].get("version")) != "1":
            raise ValueError("signal schema requires one version-1 CAN profile")
        can_ids = items[0].get("can_ids")
        body = can_ids.get(can_id) if isinstance(can_ids, dict) else None
        signals = body.get("signals") if isinstance(body, dict) else None
        if not isinstance(signals, dict) or not signals:
            raise ValueError(f"CAN profile has no signals for CAN-ID {can_id}")
        yield create_signal_schema(
            can_id=can_id,
            signal_columns=tuple(signals),
            source_digests=values.get("source_digests") or (),
        ).model_dump(mode="json")


def _reject_unknown(values: dict[str, Any], allowed: frozenset[str], name: str) -> None:
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unsupported {name} configuration: {sorted(unknown)}")


__all__ = [
    "CanPriorPolicyStageAdapter", "CanSignalSchemaStageAdapter",
    "PRIOR_NUMERIC_FIELDS",
]

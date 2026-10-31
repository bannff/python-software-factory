"""Keystone CAN pipeline helpers — pure I/O and stage construction.

Kept separate from ``can_keystone.py`` per the <200 LOC tenet.
"""
from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

from .adapters.jsonl_to_npy import load_jsonl_windows
from .can_keystone_dataset_payload import (
    build_dataset_request,
    digest,
    uri_to_path,
    write_snapshot,
)
from .can_artifact_refs import CanDatasetArtifactRef
from .can_passports import CanPassportContext
from .ports import TimeSeriesModelConfig, TimeSeriesModelType

logger = logging.getLogger(__name__)


def _get_invoker() -> Any:
    try:
        from factory.mcp_utils.interface import get_service
        return get_service("tool_invoker")
    except Exception:
        return None


def collect_mf4_files(mf4_dir: str) -> list[str]:
    """Recursive glob for MF4 files; returns absolute paths."""
    p = Path(mf4_dir)
    return [str(x.resolve()) for x in sorted({*p.rglob("*.MF4"), *p.rglob("*.mf4")})]


def reservoir_sample(records: list[dict], k: int, seed: int = 42) -> list[dict]:
    """Algorithm R reservoir sample (deterministic) down to ``k`` elements."""
    if len(records) <= k:
        return list(records)
    rng = random.Random(seed)
    reservoir = list(records[:k])
    for i, record in enumerate(records[k:], start=k):
        j = rng.randint(0, i)
        if j < k:
            reservoir[j] = record
    return reservoir


def write_sampled_jsonl(
    records: list[dict], snapshots_dir: Path, label: str,
) -> str:
    """Write sampled records as a content-addressed JSONL; return its file URI."""
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in records
    ).encode()
    d = digest(payload)
    path = snapshots_dir / f"keystone-{label}-sampled-{d}.jsonl"
    if not path.exists():
        path.write_bytes(payload)
    return path.resolve().as_uri()


def train_top_can_ids(
    trainer: Any,
    augmented_uri: str,
    top_n: int,
    vehicle_id: str,
    snapshots_dir: Path,
    model_types: list[TimeSeriesModelType] | list[str] | None = None,
    *,
    runtime: Any,
    source_digests: list[str] | None = None,
    signal_schema_refs: dict[str, CanDatasetArtifactRef],
    prior_data_policy_ref: CanDatasetArtifactRef,
    passport_context: CanPassportContext | None = None,
    require_passport: bool = False,
    model_configs: dict[TimeSeriesModelType, TimeSeriesModelConfig | None] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Train and bind one immutable feature contract per selected CAN-ID."""
    from .can_contract_training import train_can_contracts
    return train_can_contracts(
        trainer=trainer, runtime=runtime, augmented_uri=augmented_uri,
        top_n=top_n, vehicle_id=vehicle_id, snapshots_dir=snapshots_dir,
        model_types=model_types, source_digests=list(source_digests or []),
        signal_schema_refs=signal_schema_refs,
        prior_data_policy_ref=prior_data_policy_ref,
        passport_context=passport_context, require_passport=require_passport,
        model_configs=model_configs,
    )


__all__ = [
    "build_dataset_request",
    "collect_mf4_files",
    "digest",
    "load_jsonl_windows",
    "reservoir_sample",
    "train_top_can_ids",
    "uri_to_path",
    "write_sampled_jsonl",
    "write_snapshot",
]

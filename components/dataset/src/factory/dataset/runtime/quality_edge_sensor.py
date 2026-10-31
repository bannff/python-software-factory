"""Quality and group leakage checks for edge sensor-window datasets."""
from __future__ import annotations

import hashlib
import os
from collections import Counter
from pathlib import Path
from typing import Any

from .atomic_io import read_bytes_no_follow
from .contracts import DatasetQualityResults
from .edge_sensor_payload import validate_edge_sensor_payload
from .local_inputs import path_from_uri_no_follow
from .validation import validate_edge_sensor_window_records

_REQUIRED_SPLITS = ("train", "validation", "test")
_MAX_EDGE_SENSOR_PAYLOAD_BYTES = 16 * 1024 * 1024


def _is_lexically_contained(path: Path, roots: tuple[Path, ...]) -> bool:
    """Check the declared path before any filesystem operation or symlink follow."""
    candidate = Path(os.path.abspath(path))
    for root in roots:
        normalized_root = Path(os.path.abspath(root))
        try:
            if os.path.commonpath((str(normalized_root), str(candidate))) == str(normalized_root):
                return True
        except ValueError:
            continue
    return False


def evaluate_edge_sensor_quality(
    records: list[Any], *, allowed_local_roots: tuple[Path, ...] = (),
) -> DatasetQualityResults:
    """Validate records and emit auditable split and group-isolation evidence."""
    try:
        validated = list(validate_edge_sensor_window_records(records))
    except ValueError as error:
        validated = []
        schema = f"failed: {error}"
    else:
        schema = "passed"

    ids = [record.record_id for record in validated]
    duplicate_ids = sorted(
        record_id for record_id, count in Counter(ids).items() if count > 1
    )
    id_result = (
        f"failed: duplicate ids {duplicate_ids}" if duplicate_ids else "passed"
    )

    present_splits = {record.split for record in validated}
    missing_splits = [split for split in _REQUIRED_SPLITS if split not in present_splits]
    split_result = (
        f"failed: missing splits {missing_splits}" if missing_splits else "passed"
    )

    group_splits: dict[str, set[str]] = {}
    digest_splits: dict[str, set[str]] = {}
    unverifiable_payloads: list[str] = []
    invalid_payloads: list[str] = []
    payload_paths: list[Path | None] = []
    for record in validated:
        try:
            candidate = path_from_uri_no_follow(record.input_ref.uri)
            payload_paths.append(
                candidate if _is_lexically_contained(candidate, allowed_local_roots)
                else None
            )
        except (OSError, ValueError):
            payload_paths.append(None)
    for index, record in enumerate(validated):
        group_splits.setdefault(record.group_id, set()).add(record.split)
        digest_splits.setdefault(record.input_ref.sha256, set()).add(record.split)
        payload_path = payload_paths[index]
        if payload_path is None:
            unverifiable_payloads.append(record.record_id)
            continue
        try:
            payload = read_bytes_no_follow(
                payload_path, max_bytes=_MAX_EDGE_SENSOR_PAYLOAD_BYTES,
            )
        except (OSError, ValueError):
            unverifiable_payloads.append(record.record_id)
            continue
        if hashlib.sha256(payload).hexdigest() != record.input_ref.sha256:
            unverifiable_payloads.append(record.record_id)
            continue
        try:
            validate_edge_sensor_payload(payload, record)
        except ValueError:
            invalid_payloads.append(record.record_id)

    leaked_groups = sorted(
        group for group, splits in group_splits.items() if len(splits) > 1
    )
    isolation_result = (
        f"failed: groups cross splits {leaked_groups}"
        if leaked_groups else "passed"
    )
    leaked_digests = sorted(
        digest for digest, splits in digest_splits.items() if len(splits) > 1
    )
    digest_isolation = (
        f"failed: input digests cross splits {leaked_digests}"
        if leaked_digests else "passed"
    )
    payload_integrity = (
        f"failed: payloads unverified or digest-mismatched {sorted(unverifiable_payloads)}"
        if unverifiable_payloads else "passed: referenced payload bytes match SHA-256"
    )
    payload_semantics = (
        f"failed: invalid payload shape, time, values, modality, or label horizon "
        f"{sorted(invalid_payloads)}"
        if invalid_payloads else "passed: payload shape, order, values, and future label horizon"
    )
    record_count = f"passed: {len(records)}" if records else "failed: 0 records"

    return DatasetQualityResults(checks={
        "record_count": record_count,
        "schema": schema,
        "record_ids": id_result,
        "required_splits": split_result,
        "group_split_isolation": isolation_result,
        "input_digest_split_isolation": digest_isolation,
        "payload_integrity": payload_integrity,
        "payload_semantics": payload_semantics,
    })

"""Canonical acquisition evidence for immutable Chronos-2 trees."""
from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

from .adapters.chronos_identity import (
    MODEL_CLASS, MODEL_ID, MODEL_REVISION, PIPELINE_CLASS,
    PIPELINE_IMPLEMENTATION_CLASS, acquisition_package_versions,
)
from .passport_validation import canonical_json

ACQUISITION_FILENAME = "factory_acquisition.json"


def acquisition_document(resolved_commit: str) -> dict[str, Any]:
    """Build the closed contract from literal identity and current packages."""
    if resolved_commit != MODEL_REVISION:
        raise ValueError("Chronos observed resolved commit differs from requested revision")
    return {
        "schema_version": "1.0",
        "model_id": MODEL_ID,
        "requested_revision": MODEL_REVISION,
        "observed_resolved_commit": resolved_commit,
        "pipeline_class": PIPELINE_CLASS,
        "pipeline_implementation_class": PIPELINE_IMPLEMENTATION_CLASS,
        "model_class": MODEL_CLASS,
        "packages": acquisition_package_versions(),
    }


def write_acquisition_document(root: str | Path, pipeline: object) -> None:
    """Verify remote resolution and write canonical evidence before sealing."""
    model = getattr(pipeline, "inner_model", None)
    config = getattr(model, "config", None)
    observed = getattr(config, "_commit_hash", None)
    document = acquisition_document(observed)
    actual_classes = (
        _class_identity(pipeline), _class_identity(model),
    )
    if actual_classes != (PIPELINE_IMPLEMENTATION_CLASS, MODEL_CLASS):
        raise ValueError("Chronos acquired pipeline or model class is not exact")
    target = Path(root) / ACQUISITION_FILENAME
    with target.open("xb") as stream:
        stream.write(canonical_json(document))


def validate_acquisition_document(root: str | Path) -> dict[str, Any]:
    """Verify canonical bytes, literal acquisition facts, and current packages."""
    path = Path(root) / ACQUISITION_FILENAME
    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError("Chronos acquisition evidence must be a regular file")
        raw = path.read_bytes()
        document = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Chronos acquisition evidence is unreadable") from exc
    expected = acquisition_document(MODEL_REVISION)
    if document != expected:
        raise ValueError("Chronos acquisition evidence or package versions are not exact")
    if raw != canonical_json(expected):
        raise ValueError("Chronos acquisition evidence is not canonical")
    return document


def _class_identity(value: object) -> str:
    return f"{type(value).__module__}.{type(value).__name__}"


__all__ = [
    "ACQUISITION_FILENAME", "acquisition_document",
    "validate_acquisition_document", "write_acquisition_document",
]

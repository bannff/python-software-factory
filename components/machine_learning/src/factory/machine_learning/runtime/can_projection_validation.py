"""Trusted training-to-promotion binding checks for CAN projection."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .can_legacy_binding import build_can_legacy_binding


def require_training_bindings(
    training_terminal: dict[str, Any], loaded: list[tuple[Any, Any, Any]],
) -> None:
    """Cross-check revision-two passports against trusted Dataset/training truth."""
    if training_terminal.get("status") != "completed":
        raise ValueError("pipeline projection requires completed training")
    dataset = training_terminal.get("dataset_terminal")
    rows = training_terminal.get("portfolio")
    if not isinstance(dataset, dict) or not isinstance(rows, list) or not rows:
        raise ValueError("training terminal lacks trusted portfolio bindings")
    expected = sorted(rows, key=lambda row: int(row["rank"]))
    if len(expected) != len(loaded):
        raise ValueError("promotion portfolio differs from trusted training")
    for row, (binding, ref, passport) in zip(expected, loaded, strict=True):
        legacy = build_can_legacy_binding(
            dataset, can_id=str(row["can_id"]), rank=int(row["rank"]), row=row,
        )
        refs = row["artifact_refs"]
        if (
            ref.passport_revision != 2
            or passport.passport_revision != 2
            or passport.model_id != str(row["job_id"])
            or passport.final_metrics != {
                str(key): float(value) for key, value in row["metrics"].items()
            }
            or binding != legacy
            or passport.preparation.feature_contract.digest
            != str(row["contract_digest"])
            or passport.preparation.x.digest != str(refs["x_2d"]["sha256"])
            or passport.preparation.y.digest != str(refs["y"]["sha256"])
            or passport.model_artifact.uri != _file_uri(str(row["model_path"]))
            or passport.model_artifact.digest
            != str(row["artifact_seal"]["model_tree_sha256"])
        ):
            raise ValueError("promoted passport disagrees with trusted training")


def _file_uri(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme == "file":
        return value
    if parsed.scheme:
        raise ValueError("trusted training model path is not local")
    return Path(value).expanduser().absolute().as_uri()


__all__ = ["require_training_bindings"]

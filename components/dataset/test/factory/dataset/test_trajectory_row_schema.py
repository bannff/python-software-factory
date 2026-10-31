"""Frozen trajectory-row v1 contract tests (fresh file, guardian ratchet safe)."""
from __future__ import annotations

import pytest

from factory.dataset.interface import (
    TrajectoryRow, TrajectoryRowError, validate_trajectory_row,
)

_DIGEST = "sha256:" + "0" * 64


def _row(**overrides) -> dict:
    row = {
        "schema_version": 1, "run_id": "run-9", "attempt_id": "attempt-1",
        "recorded_at": "2026-10-12T00:00:00.000Z", "content_sha256": _DIGEST,
        "verdict": "scored",
    }
    row.update(overrides)
    return {key: value for key, value in row.items() if value is not None}


def test_happy_row_validates_and_round_trips() -> None:
    parsed = validate_trajectory_row(_row())
    assert isinstance(parsed, TrajectoryRow)
    assert parsed.run_id == "run-9" and parsed.attempt_id == "attempt-1"
    assert parsed.content_sha256 == _DIGEST


def test_adversarial_row_with_pii_keys_is_rejected_loudly() -> None:
    adversarial = _row(
        user_id="u-42", tenant_id="tenant-x", principal_id="p-1",
        nick="daniel", text="raw chat content", display_name="Name",
    )
    with pytest.raises(TrajectoryRowError) as excinfo:
        validate_trajectory_row(adversarial)
    message = str(excinfo.value)
    for leaked in ["user_id", "tenant_id", "principal_id", "nick", "text", "display_name"]:
        assert leaked in message


def test_non_digest_content_field_is_rejected() -> None:
    with pytest.raises(TrajectoryRowError, match="content_sha256"):
        validate_trajectory_row(_row(content_sha256="not-a-digest"))


def test_extra_row_keys_are_rejected() -> None:
    with pytest.raises(TrajectoryRowError, match="trajectory row rejected"):
        validate_trajectory_row(_row(unexpected_field="x"))

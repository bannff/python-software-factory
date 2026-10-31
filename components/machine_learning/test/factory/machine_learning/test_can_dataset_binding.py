"""Direct Dataset terminal envelope validation for ML's MCP-only binding."""
from __future__ import annotations

import pytest

from factory.machine_learning.runtime.can_dataset_binding import resolve_training_bundle


def _completed() -> dict:
    return {
        "schema_version": "v1", "ok": True, "error": None, "idempotency_key": None,
        "data": {
            "schema_version": "1.0", "status": "completed", "attempt_id": "a",
            "request_sha256": "a" * 64, "vehicle_id": "vehicle-1", "artifacts": {},
            "legacy_projection": {}, "training_bundle": {
                "schema_version": "1.0", "vehicle_id": "vehicle-1",
                "training_artifacts_by_can_id": {},
            },
        },
    }


def test_resolve_training_bundle_accepts_serialized_completed_terminal() -> None:
    terminal = resolve_training_bundle(lambda *_args, **_kwargs: _completed(), {"attempt_id": "a"})
    assert terminal["status"] == "completed"
    assert terminal["training_bundle"]["vehicle_id"] == "vehicle-1"


@pytest.mark.parametrize(
    "envelope, message",
    [
        ({**_completed(), "data": {**_completed()["data"], "status": "conflict", "error": "bound"}}, "not completed"),
        ({**_completed(), "data": {**_completed()["data"], "status": "failed", "error": "failed"}}, "not completed"),
        ({**_completed(), "ok": False, "data": None, "error": "failed"}, "request failed"),
        ({**_completed(), "data": None}, "request failed"),
        ({}, "invalid MCP result"),
        ({**_completed(), "data": {**_completed()["data"], "vehicle_id": "other"}}, "invalid trusted bindings"),
    ],
)
def test_resolve_training_bundle_rejects_terminal_error_envelopes(
    envelope: dict, message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_training_bundle(lambda *_args, **_kwargs: envelope, {"attempt_id": "a"})

"""MCP-only orchestration helpers for native CAN restart acceptance."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
from typing import Any

from mcp import ClientSession

from .api_restart_support import call, call_brick


def dataset_request(root: Path, capture: Path, pattern_ref: dict) -> dict[str, Any]:
    return {
        "attempt_id": "native-dataset", "mf4_dir": str(capture),
        "vehicle_id": "fixture-car", "vehicle_alias": "fixture-car",
        "vehicle_make": "Fixture", "vehicle_model": "Car", "vehicle_year": 2026,
        "failure_pattern_refs": [pattern_ref], "max_samples": 200,
        "emit_timespans": True,
        "config_overrides": {
            "synthesize": {"multiplier": 3},
            "window": {
                "window_size_ms": 100, "step_size_ms": 50,
                "grid_resolution_ms": 10, "observation_cutoff_ms": 100,
                "label_horizon_ms": 20,
            },
            "augment": {"techniques": ["jitter"], "seed": 7},
        },
    }


async def discover(session: ClientSession) -> None:
    listed_envelope = await call(session, "list_bricks")
    assert listed_envelope["ok"], listed_envelope
    listed = listed_envelope["data"]
    names = {item["name"] for item in listed["bricks"]}
    assert {"dataset", "machine_learning"} <= names
    for brick in ("dataset", "machine_learning"):
        envelope = await call(session, "get_brick_tools", {"brick_name": brick})
        assert envelope["ok"], envelope
        value = envelope["data"]
        assert value["brick"] == brick and value["count"] > 0


def _dataset_data(result: dict[str, Any]) -> dict[str, Any]:
    """Unwrap the Dataset typed MCP envelope for restart acceptance assertions."""
    assert result.get("ok") is True and isinstance(result.get("data"), dict), result
    return result["data"]


async def select_pattern(session: ClientSession, fingerprints: list[dict]) -> dict:
    catalog = _dataset_data(await call_brick(session, "dataset", "dataset_query_dbc_catalog", {}))
    assert catalog["count"] == 1 and catalog["entries"][0]["artifact_status"] == "verified"
    resolved = _dataset_data(await call_brick(session, "dataset", "dataset_resolve_dbc_candidate", {
        "vehicle_make": "Fixture", "vehicle_model": "Car", "vehicle_year": 2026,
        "message_fingerprints": fingerprints,
    }))
    assert resolved.get("status") == "resolved", resolved
    listed = _dataset_data(await call_brick(session, "dataset", "dataset_list_failure_patterns", {}))
    selected = next(item for item in listed["patterns"] if item["pattern_id"] == "coupled-drift")
    inspected = _dataset_data(await call_brick(session, "dataset", "dataset_inspect_failure_pattern", {
        "pattern_id": selected["pattern_id"], "version": selected["version"],
    }))
    assert len(inspected["roles"]) >= 2 and inspected["sources"]
    return selected


async def train_and_promote(
    session: ClientSession, *, family: str, request: dict,
    model_config: dict | None = None,
) -> dict[str, Any]:
    training_args = {
        "attempt_id": f"train-{family}", "dataset_request": request,
        "model_family": family, "top_n_can_ids": 1,
        "training_config": {
            "window_size": 10, "batch_size": 8, "epochs": 1,
            "early_stopping_patience": 1, "seed": 17,
        },
        "model_config": model_config, "experiment_name": f"restart-{family}",
    }
    trained_envelope = await call_brick(
        session, "machine_learning", "ml_train_can_portfolio", training_args,
    )
    assert trained_envelope["ok"], trained_envelope
    trained = trained_envelope["data"]
    assert trained["status"] == "completed", trained
    replay_envelope = await call_brick(
        session, "machine_learning", "ml_train_can_portfolio", training_args,
    )
    assert replay_envelope["ok"], replay_envelope
    assert replay_envelope["data"] == trained
    conflict = await call_brick(session, "machine_learning", "ml_train_can_portfolio", {
        **training_args, "training_config": {**training_args["training_config"], "seed": 18},
    })
    assert not conflict["ok"] and conflict["data"] is None
    assert "already bound to a different request" in conflict["error"]
    row = trained["portfolio"][0]
    assert row["model_family"] == family and len(row["x_shape"]) == 3
    issued_envelope = await call_brick(session, "machine_learning", "ml_issue_can_passports", {
        "attempt_id": f"issue-{family}",
        "training_terminal_ref": trained["terminal_ref"], "evaluation_pointers": [],
    })
    assert issued_envelope["ok"], issued_envelope
    issued = issued_envelope["data"]
    assert issued["status"] == "completed", issued
    candidate = issued["passport_refs"][0]
    promoted_envelope = await call_brick(
        session, "machine_learning", "ml_verify_and_promote_can_passport",
        _ref_args(candidate),
    )
    assert promoted_envelope["ok"], promoted_envelope
    promoted = promoted_envelope["data"]
    assert promoted["status"] in {"published", "existing"}, promoted
    exact = promoted["ref"]
    duplicate_envelope = await call_brick(
        session, "machine_learning", "ml_verify_and_promote_can_passport",
        _ref_args(candidate),
    )
    assert duplicate_envelope["ok"], duplicate_envelope
    duplicate = duplicate_envelope["data"]
    assert duplicate["ref"] == exact and exact["passport_revision"] == 2
    score_args = {
        "X_uri": row["artifact_refs"]["x_3d"]["uri"], **_ref_args(exact),
    }
    if family == "lnn":
        source = Path(row["artifact_refs"]["timespans"]["uri"].removeprefix("file://"))
        live = source.parent / "live-timing.npy"
        shutil.copyfile(source, live)
        score_args.update(
            live_timing_uri=live.as_uri(),
            live_timing_digest=hashlib.sha256(live.read_bytes()).hexdigest(),
        )
    score_envelope = await call_brick(
        session, "machine_learning", "ml_predict_neural_passport", score_args,
    )
    assert score_envelope["ok"], score_envelope
    score = score_envelope["data"]
    assert score["status"] == "completed", score
    return {
        "family": family, "training": trained, "row": row,
        "candidate_ref": candidate, "passport_ref": exact,
        "score_args": score_args, "warm_score": score,
    }


def _ref_args(ref: dict) -> dict:
    return {
        "model_id": ref["model_id"], "model_version": ref["model_version"],
        "passport_revision": ref["passport_revision"],
        "passport_uri": ref["uri"], "passport_digest": ref["digest"],
    }


__all__ = ["dataset_request", "discover", "select_pattern", "train_and_promote"]

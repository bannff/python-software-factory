"""Trajectory landing-zone writer tests (fresh file)."""
from __future__ import annotations

import asyncio
import os
import pathlib
import tempfile
from unittest.mock import patch

import pytest

from factory.dataset.interface import TrajectoryRowError, dataset_resolve_trajectory_zone
from factory.evals.mcp.run_record_tools import register
from factory.evals.runtime._persist_score import persist_score_result
from factory.evals.runtime.trajectory_writer import append_trajectory_row
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


def _digest(prefix: str = "0") -> str:
    return f"sha256:{prefix * 64}"


def _append(root: pathlib.Path, run_id: str = "run-a", attempt_id: str = "a1",
            prefix: str = "0", verdict: str = "scored") -> None:
    append_trajectory_row(
        root, run_id=run_id, attempt_id=attempt_id, content_sha256=_digest(prefix),
        recorded_at="2026-10-12T00:00:00.000Z", verdict=verdict,
    )


def _crashy(*args, **kwargs):
    raise RuntimeError("simulated crash mid-write")


def test_atomic_crash_rewrite_leaves_no_partial_row(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        _append(root, attempt_id="a1", prefix="1")
        _append(root, attempt_id="a2", prefix="2")
        path = root / "run-a.jsonl"
        stable = path.read_bytes()
        monkeypatch.setattr(os, "replace", _crashy)
        with pytest.raises(RuntimeError):
            _append(root, attempt_id="a3", prefix="3")
        assert path.read_bytes() == stable, "a partial row must never survive a crash"
        zone = dataset_resolve_trajectory_zone(path.resolve().as_uri())
        assert zone["row_count"] == 2


def test_replay_is_idempotent_per_attempt_and_digest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        _append(root, attempt_id="a1", prefix="1")
        _append(root, attempt_id="a1", prefix="1")
        path = root / "run-a.jsonl"
        zone = dataset_resolve_trajectory_zone(path.resolve().as_uri())
        assert zone["row_count"] == 1, "exact replay must not duplicate the row"


def test_writer_rejects_non_digest_row_loudly_at_ingress() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        with pytest.raises(TrajectoryRowError, match="content_sha256"):
            append_trajectory_row(
                root, run_id="run-bad", attempt_id="a1",
                content_sha256="inline-raw-content-not-a-digest", recorded_at="t",
            )
        assert not list(root.iterdir()), "no landing artifacts for a rejected row"


def test_persist_score_seam_lands_one_row(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TRAJECTORY_LANDING_ZONE", str(tmp_path))
    digest = _digest("5")

    def invoker(tool, **kwargs):
        assert tool == "evals_record_run"
        return {"schema_version": "v1", "ok": True, "data": {
            "persisted": True, "status": "created",
            "pointer": {"content_hash": digest},
        }, "error": None, "idempotency_key": None}

    scoring = {"precision": 1.0, "recall": 1.0, "f1": 1.0, "true_positives": 1,
               "false_positives_count": 0, "false_negatives": 0, "matched": [{}], "missed": []}
    assert persist_score_result(invoker, "run-seam", "sast", "App", "SQLi", scoring)
    zone = dataset_resolve_trajectory_zone((tmp_path / "run-seam.jsonl").resolve().as_uri())
    assert zone["row_count"] == 1
    assert zone["rows"][0]["content_sha256"] == digest


def _match_store():
    def invoker(tool: str, **kwargs):
        if tool == "storage_doc_create_or_match":
            return {"status": "created"}
        return {}

    return invoker


def test_run_record_seam_lands_row_with_default_attempt_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TRAJECTORY_LANDING_ZONE", str(tmp_path))
    mcp = ToolCatalog("records")
    register(mcp)
    tool = asyncio.run(mcp.get_tool("evals_record_run"))
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": _match_store()}):
        result = tool.fn(
            run_id="run-seam2", experiment_name="exp", verdict="PASS",
            pass_rate=1.0, avg_score=1.0, total_cases=1, passed=1,
            case_results=[{"passed": True, "score": 1.0}], case_scores=[1.0],
        ).model_dump(mode="json")["data"]
    assert result["persisted"] and result["pointer"]["content_hash"]
    zone = dataset_resolve_trajectory_zone((tmp_path / "run-seam2.jsonl").resolve().as_uri())
    assert zone["row_count"] == 1
    row = zone["rows"][0]
    assert row["attempt_id"] == "run-seam2" and row["content_sha256"] == result["content_hash"]


"""Hermetic fixture-backed acceptance for use_context=True."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.dataset.interface import dataset_get_job
from factory.mcp_server.interface import MCPAggregator
from factory.mcp_utils.interface import get_service, set_service
from factory.dataset.runtime.recipe import resolve_recipe
from factory.machine_learning.runtime import can_keystone as keystone
from factory.machine_learning.runtime.can_context_pipeline import (
    sample_corpus_for_synth as real_sample,
)
from factory.machine_learning.runtime.can_keystone_runner import (
    run_keystone_stage as real_dataset_stage,
)


@pytest.fixture
def lazy_dataset_invoker():
    """Install and restore a real progressive Dataset aggregator per test."""
    previous = get_service("tool_invoker")
    aggregator = MCPAggregator(ToolCatalog("dataset-e2e-aggregator"))
    aggregator.set_available_bricks(["dataset"])
    set_service("tool_invoker", aggregator.invoke_tool)
    yield aggregator
    set_service("tool_invoker", previous)


def _write_jsonl(path: Path, records: list[dict]) -> str:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in records))
    return path.as_uri()


def _records() -> list[dict]:
    start_ns = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1e9)
    return [
        {
            "timestamp_ns": start_ns + i * 1_000_000_000,
            "vehicle_id": "fixture-vehicle", "trip_id": "trip-1",
            "bus_name": "can0", "arbitration_id": "0x100",
            "is_extended": False, "is_fd": False, "dlc": 8,
            "data_bytes": [0] * 8, "frame_type": "data",
            "error_state": None, "source_ecu": "ecu-1",
            "capture_source": "fixture",
            "decoded_signals": {"speed": float(i + 1)},
            "dbc_message_name": "FixtureMessage",
            "is_failure": 1 if i >= 3 else 0,
            "failure_mode": "signal_drift" if i >= 3 else None,
            "failure_timestamp_ns": start_ns + i * 1_000_000_000 if i >= 3 else None,
        }
        for i in range(6)
    ]


def test_use_context_keystone_executes_real_dataset_chain(
    tmp_path, monkeypatch, lazy_dataset_invoker,
):
    decoded_uri = _write_jsonl(tmp_path / "decoded.jsonl", _records())
    profile_uri = _write_jsonl(tmp_path / "profile.jsonl", [{
        "version": "1", "can_ids": {"0x100": {"signals": {"speed": {}}}},
    }])
    context_source = tmp_path / "vehicle.json"
    start_ns = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1e9)
    context_source.write_text(json.dumps({
        "vehicle_id": "fixture-vehicle", "odometer_km": 1234,
        "battery_health_pct": 87, "observed_at_ns": start_ns,
        "available_at_ns": start_ns,
    }))
    secondary_source = tmp_path / "secondary.json"
    secondary_source.write_text("{}")
    mf4_dir = tmp_path / "mf4"
    mf4_dir.mkdir()
    (mf4_dir / "fixture.MF4").write_bytes(b"fixture")
    dbc = tmp_path / "fixture.dbc"
    dbc.write_text("VERSION \"fixture\"")
    root = tmp_path / "store"

    outer_calls: list[tuple[str, list[str]]] = []
    sample_inputs: list[str] = []

    def stage_runner(stage, recipe_uri, input_uris, config, snaps, storage, key, **kwargs):
        if (stage.startswith("context_") or stage.startswith("signal_schema:")
                or stage == "prior_policy"):
            return real_dataset_stage(
                stage, recipe_uri, input_uris, config, snaps, storage, key,
                input_roles=kwargs.get("input_roles"), poll_interval_s=0.01,
                poll_timeout_s=30,
            )
        outer_calls.append((stage, list(input_uris)))
        return {
            "job_id": f"stub-{stage}",
            "dataset_uri": profile_uri if stage == "profile" else decoded_uri,
            "manifest_uri": (tmp_path / f"{stage}.manifest.json").as_uri(),
        }

    def sample(uri, max_samples, vehicle_id, snaps):
        sample_inputs.append(uri)
        return real_sample(uri, max_samples, vehicle_id, snaps)

    monkeypatch.setattr(keystone, "run_keystone_stage", stage_runner)
    monkeypatch.setattr(keystone, "sample_corpus_for_synth", sample)
    monkeypatch.setattr(
        keystone, "resolve_can_passport_context",
        lambda *_args, **_kwargs: MagicMock(storage_root=str(root)),
    )
    monkeypatch.setattr(
        keystone, "train_top_can_ids",
        lambda *_args, **_kwargs: ([{"can_id": "0x100", "metrics": {}}], ["model-1"]),
    )

    result = keystone.run_keystone_pipeline(
        mf4_dir=str(mf4_dir), dbc_path=str(dbc), vehicle_id="fixture-vehicle",
        storage_root=root, max_samples=100, top_n_can_ids=1, use_context=True,
        context_sources=[str(context_source), str(secondary_source)], runtime=MagicMock(),
        config_overrides={
            "context_ingest": {
                "sources": ["vehicle_metadata"],
                "time_range": ["2025-01-01T00:00:00Z", "2025-01-01T00:01:00Z"],
            },
            "context_augment": {
                "context_fields": ["odometer_km", "battery_health_pct"],
                "max_time_delta_s": 60,
            },
            "context_correlate": {"method": "spearman", "min_correlation": 0.0},
        },
    )

    assert "error" not in result
    assert set(result["contract_artifacts"]) == {
        "signal_schema:0x100", "prior_data_policy",
    }
    assert all(item["digest"] for item in result["contract_artifacts"].values())
    jobs = result["context"]
    artifacts = result["context_artifacts"]
    assert list(jobs) == ["context_ingest", "context_augment", "context_correlate"]
    assert artifacts["context_augment"] != artifacts["context_correlate"]
    assert sample_inputs == [artifacts["context_augment"]]
    synth_inputs = dict(outer_calls)["synthesize"]
    assert artifacts["context_correlate"] not in synth_inputs

    statuses = {name: dataset_get_job(job_id, root) for name, job_id in jobs.items()}
    assert all(status and status.status == "completed" for status in statuses.values())
    assert [a.artifact_role for a in statuses["context_ingest"].request.input_artifacts] == [
        "decoded_can", "context_source:0", "context_source:1",
    ]
    assert [a.artifact_role for a in statuses["context_augment"].request.input_artifacts] == [
        "decoded_can", "environment_context",
    ]
    assert [a.artifact_role for a in statuses["context_correlate"].request.input_artifacts] == [
        "context_augmented_can",
    ]
    ingest_inputs = statuses["context_ingest"].request.input_artifacts
    assert ingest_inputs[0].digest != ingest_inputs[1].digest

    augmented = [
        json.loads(line) for line in Path(artifacts["context_augment"].removeprefix("file://")).read_text().splitlines()
    ]
    assert augmented and all(row["decoded_signals"] for row in augmented)
    assert all(row["context"]["odometer_km"] == 1234 for row in augmented)
    correlation = [
        json.loads(line) for line in Path(artifacts["context_correlate"].removeprefix("file://")).read_text().splitlines()
    ]
    json.dumps(correlation)
    assert correlation[-1]["record_type"] == "context_correlation_heatmap"
    assert correlation[-1]["method"] == "spearman"

    resolved = {
        name: resolve_recipe(status.request).stages[0].config
        for name, status in statuses.items()
    }
    assert resolved["context_ingest"]["vehicle_id"] == "fixture-vehicle"
    assert resolved["context_ingest"]["sources"] == ["vehicle_metadata"]
    assert resolved["context_ingest"]["input_uris"] == [
        decoded_uri, context_source.as_uri(), secondary_source.as_uri(),
    ]
    assert resolved["context_augment"]["max_time_delta_s"] == 60
    assert resolved["context_augment"]["input_uri"] == decoded_uri
    assert resolved["context_augment"]["context_uri"] == artifacts["context_ingest"]
    assert resolved["context_correlate"]["method"] == "spearman"
    assert resolved["context_correlate"]["input_uri"] == artifacts["context_augment"]
    assert len(resolved["context_correlate"]["failure_modes"]) == 8

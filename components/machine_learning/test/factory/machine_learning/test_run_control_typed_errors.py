"""Run control and checkpoint reads fail with stable codes (#448)."""
from __future__ import annotations

import asyncio
import os

import pytest

from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.machine_learning.server import create_tool_catalog


@pytest.fixture
def tools():
    catalog = create_tool_catalog(TrackingRuntime())
    return {t.name: t.fn for t in asyncio.run(catalog.list_tools())}


@pytest.mark.parametrize("name", ["ml_pause_training", "ml_resume_training", "ml_stop_at_checkpoint"])
def test_unknown_attempt_is_a_typed_code(tools, monkeypatch, tmp_path, name) -> None:
    # realpath: the passport root rejects symlink ancestors (macOS tmp is one).
    monkeypatch.setenv("ML_MODEL_PASSPORT_ROOT", os.path.realpath(tmp_path))
    assert tools[name](attempt_id="nope").error == "attempt_not_found"


def test_missing_model_root_is_a_typed_code(tools, monkeypatch) -> None:
    monkeypatch.delenv("ML_MODEL_PASSPORT_ROOT", raising=False)
    assert tools["ml_pause_training"](attempt_id="nope").error == "model_root_not_configured"


@pytest.mark.parametrize("name", ["ml_list_checkpoints", "ml_list_stage_artifacts"])
def test_unknown_job_is_a_typed_code(tools, name) -> None:
    assert tools[name](job_id="nope").error == "job_not_found"

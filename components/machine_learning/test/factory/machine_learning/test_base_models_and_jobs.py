from __future__ import annotations

import asyncio

import pytest

from factory.machine_learning.mcp import authoring
from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.machine_learning.server import create_tool_catalog

DIGEST = "a" * 64


@pytest.fixture
def tools(monkeypatch):
    monkeypatch.setenv("ML_ENABLE_AUTHORING_TOOLS", "1")
    monkeypatch.setattr(authoring, "_model_registry", {})
    catalog = create_tool_catalog(TrackingRuntime())
    return {t.name: t.fn for t in asyncio.run(catalog.list_tools())}


def _job(tools, base_model="base-1", digest=DIGEST):
    return tools["ml_create_finetuning_job"](
        method="lora", base_model=base_model, dataset_uri="s3://b/d", manifest_uri="s3://b/m",
        dataset_digest=digest, view_name="v", view_schema_version="1")


def test_base_model_list_update_delete(tools) -> None:
    tools["ml_register_base_model"](name="base-1", model_id="org/m")
    assert tools["ml_list_base_models"]().data.count == 1
    upd = tools["ml_update_base_model"](name="base-1", description="d")
    assert upd.data.model.description == "d" and upd.data.model.model_id == "org/m"
    assert tools["ml_update_base_model"](name="nope", description="d").error == "base_model_not_found"
    job = _job(tools)
    assert job.ok
    assert tools["ml_delete_base_model"](name="base-1").error == "base_model_in_use"
    assert tools["ml_delete_finetuning_job"](job_id=job.data.id).ok
    assert tools["ml_delete_base_model"](name="base-1").data.deleted
    assert tools["ml_delete_base_model"](name="base-1").error == "base_model_not_found"


def test_delete_job_is_typed(tools) -> None:
    assert tools["ml_delete_finetuning_job"](job_id="missing").error == "job_not_found"


def test_invalid_job_input_is_typed_not_opaque(tools) -> None:
    assert _job(tools, digest="short").error == "finetuning_input_invalid"
    bad = tools["ml_create_finetuning_job"](
        method="nope", base_model="b", dataset_uri="s3://b/d", manifest_uri="s3://b/m",
        dataset_digest=DIGEST, view_name="v", view_schema_version="1")
    assert bad.error == "finetuning_input_invalid"

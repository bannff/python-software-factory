from __future__ import annotations

import asyncio
import hashlib

import pytest

from factory.machine_learning.runtime import dataset_registry
from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.machine_learning.server import create_tool_catalog


@pytest.fixture
def tools(monkeypatch):
    monkeypatch.setattr(dataset_registry, "REGISTRY", dataset_registry.DatasetRegistry())
    import factory.machine_learning.mcp.dataset_tools as module
    monkeypatch.setattr(module, "REGISTRY", dataset_registry.REGISTRY)
    catalog = create_tool_catalog(TrackingRuntime())
    return {t.name: t for t in asyncio.run(catalog.list_tools())}


def _args(name="d1", uri="s3://b/d.jsonl", digest="sha256:" + "a" * 64):
    return dict(name=name, uri=uri, manifest_uri="s3://b/m.json", digest=digest,
                view_name="v", view_schema_version="1")


def test_register_get_update_delete_with_typed_errors(tools) -> None:
    add = tools["ml_register_dataset"].fn
    assert add(**_args()).data.dataset.revision == 1
    assert add(**_args()).error == "dataset_exists"
    assert tools["ml_get_dataset"].fn(dataset_id="nope").error == "dataset_not_found"
    assert tools["ml_update_dataset"].fn(
        dataset_id="d1", description="x", expected_revision=5).error == "dataset_revision_conflict"
    upd = tools["ml_update_dataset"].fn(dataset_id="d1", description="x", expected_revision=1)
    assert upd.data.dataset.revision == 2 and upd.data.dataset.description == "x"
    assert tools["ml_list_datasets"].fn().data.count == 1
    assert tools["ml_delete_dataset"].fn(dataset_id="d1").data.deleted
    assert tools["ml_delete_dataset"].fn(dataset_id="d1").error == "dataset_not_found"


def test_digest_is_checked_against_a_local_file(tools, tmp_path) -> None:
    f = tmp_path / "d.jsonl"
    f.write_text("{}\n")
    good = "sha256:" + hashlib.sha256(f.read_bytes()).hexdigest()
    add = tools["ml_register_dataset"].fn
    assert add(**_args(uri=str(f), digest="sha256:" + "0" * 64)).error == "dataset_digest_mismatch"
    assert add(**_args(uri=str(f), digest=good)).ok
    assert add(**_args(name="d2", digest="bad")).error == "dataset_digest_mismatch"
    assert add(**_args(name="BAD NAME")).error == "dataset_invalid"


def test_dataset_in_use_by_a_job_cannot_be_deleted(tools) -> None:
    tools["ml_register_dataset"].fn(**_args(uri="s3://b/used"))
    job = tools["ml_create_finetuning_job"].fn(
        method="lora", base_model="b", dataset_uri="s3://b/used", manifest_uri="s3://b/m.json",
        dataset_digest="a" * 64, view_name="v", view_schema_version="1")
    assert job.ok
    assert tools["ml_delete_dataset"].fn(dataset_id="d1").error == "dataset_in_use"
    assert tools["ml_delete_finetuning_job"].fn(job_id=job.data.id).ok
    assert tools["ml_delete_dataset"].fn(dataset_id="d1").data.deleted


def test_job_accepts_dataset_id_and_prefixed_digest(tools) -> None:
    tools["ml_register_dataset"].fn(**_args(uri="s3://b/by-id", digest="sha256:" + "b" * 64))
    job = tools["ml_create_finetuning_job"].fn(method="lora", base_model="b", dataset_id="d1")
    assert job.ok and job.data.training_input["dataset_digest"] == "b" * 64
    prefixed = tools["ml_create_finetuning_job"].fn(
        method="lora", base_model="b", dataset_uri="s3://b/x", manifest_uri="s3://b/m",
        dataset_digest="sha256:" + "c" * 64, view_name="v", view_schema_version="1")
    assert prefixed.ok
    assert tools["ml_create_finetuning_job"].fn(method="lora", base_model="b").error == "finetuning_input_invalid"
    assert tools["ml_create_finetuning_job"].fn(
        method="lora", base_model="b", dataset_id="nope").error == "dataset_not_found"

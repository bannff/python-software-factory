"""Fail-closed Dataset ToolResult checks for passport lineage consumers."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from factory.machine_learning.runtime.adapters.model_passport_verifier import LocalModelPassportVerifier
from factory.machine_learning.runtime.can_passports import resolve_can_passport_context
from factory.mcp_utils.interface import get_service, set_service

from .passport_fixtures import passport, passport_invoker


def _envelope(data, *, ok=True, error=None):
    return {"schema_version": "v1", "ok": ok, "data": data, "error": error, "idempotency_key": None}


def _artifact(root: Path, name: str) -> dict[str, str]:
    dataset = root / "artifacts" / name / "dataset.jsonl"
    manifest = root / "manifests" / f"{name}.json"
    dataset.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    dataset.write_text("{}\n")
    manifest.write_text("{}")
    return {"dataset_uri": dataset.as_uri(), "manifest_uri": manifest.as_uri(), "digest": hashlib.sha256(dataset.read_bytes()).hexdigest()}


@pytest.fixture(autouse=True)
def restore_invoker():
    previous = get_service("tool_invoker")
    yield
    set_service("tool_invoker", previous)


@pytest.mark.parametrize("response", [None, {}, _envelope(None), _envelope(None, ok=False, error="failed")])
def test_resolve_can_passport_context_rejects_non_success_envelopes(tmp_path: Path, response):
    training, synthesis = _artifact(tmp_path / "dataset", "training"), _artifact(tmp_path / "dataset", "synthesis")
    set_service("tool_invoker", lambda *_args, **_kwargs: response)
    with pytest.raises(ValueError, match="Dataset MCP verification failed"):
        resolve_can_passport_context(training, synthesis, passport_storage_root=tmp_path / "passports", dataset_storage_root=tmp_path / "dataset")


def test_resolve_can_passport_context_rejects_manifest_mismatch(tmp_path: Path):
    training, synthesis = _artifact(tmp_path / "dataset", "training"), _artifact(tmp_path / "dataset", "synthesis")
    def invoke(_name, **kwargs):
        artifact = training if kwargs["dataset_uri"] == training["dataset_uri"] else synthesis
        return _envelope({**artifact, "dataset_digest": "wrong"})
    set_service("tool_invoker", invoke)
    with pytest.raises(ValueError, match="manifest disagrees"):
        resolve_can_passport_context(training, synthesis, passport_storage_root=tmp_path / "passports", dataset_storage_root=tmp_path / "dataset")


@pytest.mark.parametrize("response", [None, {}, _envelope(None), _envelope(None, ok=False, error="failed")])
def test_passport_verifier_rejects_non_success_dataset_envelopes(tmp_path: Path, response):
    value = passport(tmp_path)
    verifier = LocalModelPassportVerifier(tmp_path, lambda *_args, **_kwargs: response)
    with pytest.raises(ValueError, match="dataset_resolve_artifact verification failed"):
        verifier.verify(value)


def test_passport_verifier_rejects_manifest_mismatch(tmp_path: Path):
    value = passport(tmp_path)
    invoker = passport_invoker(value)
    def mismatch(*args, **kwargs):
        response = invoker(*args, **kwargs)
        response["data"]["dataset_digest"] = "wrong"
        return response
    with pytest.raises(ValueError, match="manifest disagrees"):
        LocalModelPassportVerifier(tmp_path, mismatch).verify(value)

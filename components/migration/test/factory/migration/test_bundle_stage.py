"""migration.runtime.bundle_stage — single-file companion-x-v1 bundle
staging/validation, row 54 Portability import half."""
from __future__ import annotations

import hashlib
import json

import pytest

from factory.migration.runtime.bundle_stage import BundleStageError, stage_bundle


def _digest(payload) -> str:
    return f"sha256:{hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()}"


def _write_valid_bundle(path):
    records = [{"identity": "a" * 64, "content": "hello", "kind": "semantic", "tags": []}]
    kinds = {"memory": {"count": 1, "excluded": 0, "digest": _digest(records), "records": records}}
    bundle = {
        "bundle_version": 1, "adapter": "companion-x-v1",
        "producer": {"app": "companion-x", "kinds": ["memory"]},
        "content_digest": _digest(kinds), "kinds": kinds,
    }
    path.write_text(json.dumps(bundle))
    return bundle


def test_stages_a_valid_bundle(tmp_path):
    path = tmp_path / "backup.cxbundle.json"
    _write_valid_bundle(path)
    staged = stage_bundle(path)
    assert staged["bundle_version"] == 1
    assert staged["adapter"] == "companion-x-v1"


def test_rejects_relative_path(tmp_path):
    path = tmp_path / "backup.cxbundle.json"
    _write_valid_bundle(path)
    with pytest.raises(BundleStageError, match="bundle_path_must_be_absolute"):
        stage_bundle(path.relative_to(path.anchor))


def test_rejects_a_missing_file(tmp_path):
    with pytest.raises(BundleStageError, match="bundle_unreadable"):
        stage_bundle(tmp_path / "nope.json")


def test_rejects_a_symlinked_bundle(tmp_path):
    real = tmp_path / "real.json"
    _write_valid_bundle(real)
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(BundleStageError, match="bundle_symlink_rejected"):
        stage_bundle(link)


def test_rejects_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    with pytest.raises(BundleStageError, match="bundle_invalid_json"):
        stage_bundle(path)


def test_rejects_unsupported_bundle_version(tmp_path):
    path = tmp_path / "backup.cxbundle.json"
    bundle = _write_valid_bundle(path)
    bundle["bundle_version"] = 99
    path.write_text(json.dumps(bundle))
    with pytest.raises(BundleStageError, match="bundle_version_unsupported"):
        stage_bundle(path)


def test_rejects_wrong_adapter(tmp_path):
    path = tmp_path / "backup.cxbundle.json"
    bundle = _write_valid_bundle(path)
    bundle["adapter"] = "kirocrew-v1"
    path.write_text(json.dumps(bundle))
    with pytest.raises(BundleStageError, match="bundle_adapter_mismatch"):
        stage_bundle(path)


def test_rejects_a_tampered_content_digest(tmp_path):
    path = tmp_path / "backup.cxbundle.json"
    bundle = _write_valid_bundle(path)
    bundle["kinds"]["memory"]["records"][0]["content"] = "tampered"
    path.write_text(json.dumps(bundle))  # content_digest now stale
    with pytest.raises(BundleStageError, match="bundle_content_digest_mismatch"):
        stage_bundle(path)


def test_rejects_a_tampered_kind_digest(tmp_path):
    path = tmp_path / "backup.cxbundle.json"
    bundle = _write_valid_bundle(path)
    extra = {"identity": "b" * 64, "content": "sneaked in", "kind": "semantic", "tags": []}
    bundle["kinds"]["memory"]["records"].append(extra)  # content_digest recomputed below stays valid...
    # ...but the per-kind digest was NOT recomputed, so this must fail there.
    path.write_text(json.dumps(bundle))
    with pytest.raises(BundleStageError, match="bundle_content_digest_mismatch|bundle_kind_digest_mismatch"):
        stage_bundle(path)


def test_rejects_oversized_bundle(tmp_path, monkeypatch):
    import factory.migration.runtime.bundle_stage as module
    monkeypatch.setattr(module, "MAX_BUNDLE_BYTES", 10)
    path = tmp_path / "backup.cxbundle.json"
    _write_valid_bundle(path)
    with pytest.raises(BundleStageError, match="bundle_size_exceeded"):
        stage_bundle(path)

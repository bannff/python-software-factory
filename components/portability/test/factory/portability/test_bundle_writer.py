"""portability.runtime.bundle_writer — owner-scoped, path-contained,
atomic bundle write. Row 54 Portability."""
from __future__ import annotations

import json
import os

import pytest

from factory.portability.runtime.bundle_writer import (
    BundleWriteError, resolve_destination, write_bundle,
)


@pytest.fixture
def export_root(tmp_path, monkeypatch):
    root = tmp_path / "exports"
    monkeypatch.setenv("PORTABILITY_EXPORT_ROOT", str(root))
    return root


def test_resolve_destination_creates_the_root_and_returns_a_path_inside_it(export_root):
    dest = resolve_destination("backup.cxbundle.json")
    assert dest.parent == export_root.resolve()
    assert export_root.is_dir()


def test_resolve_destination_rejects_path_separators(export_root):
    with pytest.raises(BundleWriteError, match="portability_export_name_invalid"):
        resolve_destination("../escape.json")
    with pytest.raises(BundleWriteError, match="portability_export_name_invalid"):
        resolve_destination("sub/dir.json")


def test_resolve_destination_rejects_a_symlinked_existing_target(export_root, tmp_path):
    export_root.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    link = export_root / "link.json"
    link.symlink_to(outside)
    with pytest.raises(BundleWriteError, match="portability_export_symlink_rejected"):
        resolve_destination("link.json")


def test_missing_export_root_env_raises_typed_error(monkeypatch):
    monkeypatch.delenv("PORTABILITY_EXPORT_ROOT", raising=False)
    with pytest.raises(BundleWriteError, match="portability_export_root_not_configured"):
        resolve_destination("backup.json")


def test_relative_export_root_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTABILITY_EXPORT_ROOT", "relative/path")
    with pytest.raises(BundleWriteError, match="portability_export_root_must_be_absolute"):
        resolve_destination("backup.json")


def test_write_bundle_is_atomic_and_readable(export_root):
    dest = resolve_destination("backup.cxbundle.json")
    written = write_bundle(dest, {"bundle_version": 1, "kinds": {}})
    assert dest.exists()
    assert written == len(dest.read_bytes())
    loaded = json.loads(dest.read_text())
    assert loaded["bundle_version"] == 1
    # no leftover temp file
    assert [p.name for p in export_root.iterdir()] == ["backup.cxbundle.json"]


def test_write_bundle_overwrites_cleanly_on_re_export(export_root):
    dest = resolve_destination("backup.cxbundle.json")
    write_bundle(dest, {"bundle_version": 1, "kinds": {"a": 1}})
    write_bundle(dest, {"bundle_version": 1, "kinds": {"a": 2}})
    assert json.loads(dest.read_text())["kinds"]["a"] == 2
    assert [p.name for p in export_root.iterdir()] == ["backup.cxbundle.json"]

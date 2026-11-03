from __future__ import annotations

import os
import tempfile

import pytest

# Module-level registries are built at import time; keep that out of the real home dir.
os.environ.setdefault("ML_REGISTRY_DIR", tempfile.mkdtemp(prefix="ml-registry-"))


@pytest.fixture(autouse=True)
def _isolated_registry_dir(tmp_path, monkeypatch):
    """Each test gets its own registry directory so persisted state never leaks."""
    monkeypatch.setenv("ML_REGISTRY_DIR", str(tmp_path / "registry"))

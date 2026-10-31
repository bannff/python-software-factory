"""Pytest bootstrap for source-first imports in the Polylith workspace."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _prepend_workspace_src_paths() -> None:
    root = Path(__file__).resolve().parent
    src_paths: list[str] = []

    for group in ("bases", "components"):
        group_dir = root / group
        if not group_dir.is_dir():
            continue
        for child in sorted(group_dir.iterdir()):
            src_dir = child / "src"
            if src_dir.is_dir():
                src_paths.append(str(src_dir))

    for src_path in reversed(src_paths):
        if src_path in sys.path:
            sys.path.remove(src_path)
        sys.path.insert(0, src_path)


_prepend_workspace_src_paths()


@pytest.fixture(autouse=True)
def _pin_memory_tracker_backend(monkeypatch):
    """Keep tracker selection hermetic: the suite relies on the memory
    backend's fabricated seed-hash metrics. ML_TRACKER_BACKEND stays an
    opt-in per-env flip, never a test default."""
    monkeypatch.setenv("ML_TRACKER_BACKEND", "memory")


@pytest.fixture(autouse=True)
def _isolate_mcp_service_registry():
    """Snapshot and restore the mcp_utils service registry around each test.

    ``create_configured_native_server()`` registers process-global callbacks
    (notably ``mcp_token_verifier``) through ``factory.mcp_utils.registry``.
    Without isolation, any test that builds the app leaks them, and later
    tests that rely on their own mocks silently take the real branch — e.g.
    ``ag_ui_identity.extract_identity`` preferring a leaked verifier over the
    test's mocked aggregator.
    """
    from factory.mcp_utils import registry

    snapshot = dict(registry._services)
    try:
        yield
    finally:
        registry._services.clear()
        registry._services.update(snapshot)

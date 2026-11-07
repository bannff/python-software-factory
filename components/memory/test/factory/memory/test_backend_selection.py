"""Memory backend selection must not silently accept a retired backend.

A-MEM (``MEMORY_BACKEND=amem``) shipped with the retired ChromaDB adapters.
An unknown value now logs an error and falls back to the in-process store
instead of quietly pretending the request was honoured.
"""
from __future__ import annotations

import logging

from factory.memory import server
from factory.memory.runtime.runtime import MemoryRuntime


def _patch_backend(monkeypatch, value: str) -> None:
    import factory.mcp_utils.config_helpers as helpers
    monkeypatch.setattr(
        helpers, "get_infra",
        lambda key, default=None: value if key == "memory.backend" else default,
    )


def test_known_backend_is_silent(monkeypatch, caplog) -> None:
    _patch_backend(monkeypatch, "memory")

    with caplog.at_level(logging.ERROR):
        runtime = server._default_runtime()

    assert isinstance(runtime, MemoryRuntime)
    assert "unsupported memory.backend" not in caplog.text


def test_retired_amem_backend_logs_and_falls_back(monkeypatch, caplog) -> None:
    _patch_backend(monkeypatch, "amem")

    with caplog.at_level(logging.ERROR):
        runtime = server._default_runtime()

    assert isinstance(runtime, MemoryRuntime)
    assert "unsupported memory.backend 'amem'" in caplog.text

"""KB backend selection must fail closed on an unknown ``kb.backend``.

Chroma is a retired backend: it stays reachable only when asked for by name.
Before this, any unknown value (a typo, ``local``, an old ``chromadb`` alias)
fell through to Chroma and silently re-enabled it.
"""
from __future__ import annotations

import logging

import pytest

import factory.config.interface as config_interface
from factory.kb import server
from factory.kb.runtime.runtime import KBRuntime


def _patch_backend(monkeypatch, value: str | None) -> None:
    monkeypatch.setattr(
        config_interface, "get_infra",
        lambda key, default=None: value if value is not None else default,
    )
    monkeypatch.setattr(config_interface, "get_neo4j_config", lambda: {"uri": "bolt://stub"})


def _record(monkeypatch) -> dict[str, str]:
    calls: dict[str, str] = {}

    def fake_neo4j(runtime: KBRuntime, get_neo4j_config) -> None:
        calls["neo4j"] = "neo4j"

    def fake_chroma(runtime: KBRuntime, get_infra) -> None:
        calls["chroma"] = "chroma"

    monkeypatch.setattr(server, "_configure_neo4j", fake_neo4j)
    monkeypatch.setattr(server, "_configure_chroma", fake_chroma)
    return calls


def test_default_backend_is_neo4j(monkeypatch, tmp_path) -> None:
    _patch_backend(monkeypatch, None)
    calls = _record(monkeypatch)

    server._configure_vector_store(KBRuntime(tmp_path))

    assert calls == {"neo4j": "neo4j"}


@pytest.mark.parametrize("value", ["chromadb", "chroma"])
def test_chroma_is_reachable_only_by_explicit_name(monkeypatch, tmp_path, value) -> None:
    _patch_backend(monkeypatch, value)
    calls = _record(monkeypatch)

    server._configure_vector_store(KBRuntime(tmp_path))

    assert calls == {"chroma": "chroma"}


@pytest.mark.parametrize("value", ["chroma2", "local", "nope", ""])
def test_unknown_backend_fails_closed(monkeypatch, tmp_path, caplog, value) -> None:
    _patch_backend(monkeypatch, value)
    calls = _record(monkeypatch)
    runtime = KBRuntime(tmp_path)

    with caplog.at_level(logging.ERROR):
        server._configure_vector_store(runtime)

    assert calls == {}, "an unknown backend must not configure a store"
    assert runtime.backend_name is None
    assert "unsupported kb.backend" in caplog.text

"""KB backend selection accept exactly three backends and fails closed otherwise.

ChromaDB was retired in #353: its adapters and the ``chromadb`` dependency are
gone. Any value outside ``neo4j``/``graph``/``bedrock`` — a typo, ``local``, or
the old ``chromadb``/``chroma`` aliases — must configure no store at all rather
than silently selecting one.
"""
from __future__ import annotations

import logging

import pytest

import factory.config.interface as config_interface
from factory.kb.runtime import vector_store_selection as selection
from factory.kb.runtime.runtime import KBRuntime

SUPPORTED_BACKENDS = {"neo4j", "graph", "bedrock"}


def _patch_backend(monkeypatch, value: str | None) -> None:
    monkeypatch.setattr(
        config_interface, "get_infra",
        lambda key, default=None: value if value is not None else default,
    )
    monkeypatch.setattr(
        config_interface, "get_neo4j_config", lambda: {"uri": "bolt://stub"},
    )


def _record(monkeypatch) -> dict[str, str]:
    calls: dict[str, str] = {}

    def recorder(name):
        def fake(runtime: KBRuntime, *args) -> None:
            calls[name] = name
        return fake

    monkeypatch.setattr(selection, "_configure_neo4j", recorder("neo4j"))
    monkeypatch.setattr(selection, "_configure_graph", recorder("graph"))
    monkeypatch.setattr(selection, "_configure_bedrock", recorder("bedrock"))
    return calls


def test_only_the_three_backends_are_known() -> None:
    assert set(selection._KNOWN_BACKENDS) == SUPPORTED_BACKENDS


def test_default_backend_is_neo4j(monkeypatch, tmp_path) -> None:
    _patch_backend(monkeypatch, None)
    calls = _record(monkeypatch)

    selection.configure_vector_store(KBRuntime(tmp_path))

    assert calls == {"neo4j": "neo4j"}


@pytest.mark.parametrize("value", sorted(SUPPORTED_BACKENDS))
def test_supported_backends_configure_their_store(monkeypatch, tmp_path, value) -> None:
    _patch_backend(monkeypatch, value)
    calls = _record(monkeypatch)

    selection.configure_vector_store(KBRuntime(tmp_path))

    assert calls == {value: value}


@pytest.mark.parametrize("value", ["chromadb", "chroma", "chroma2", "local", "nope", ""])
def test_unsupported_backend_fails_closed(monkeypatch, tmp_path, caplog, value) -> None:
    _patch_backend(monkeypatch, value)
    calls = _record(monkeypatch)
    runtime = KBRuntime(tmp_path)

    with caplog.at_level(logging.ERROR):
        selection.configure_vector_store(runtime)

    assert calls == {}, "an unsupported backend must not configure a store"
    assert runtime.backend_name is None
    assert "unsupported kb.backend" in caplog.text
    assert "bedrock, graph, neo4j" in caplog.text

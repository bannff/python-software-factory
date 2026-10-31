"""M7.7 Slice 1 (KB half) — local embedder: real path when available, honest fallback."""
from __future__ import annotations

from factory.kb.runtime.retrieval.embedding_local import LocalKBEmbedder


def test_falls_back_when_no_model_path_configured() -> None:
    embedder = LocalKBEmbedder(model_path="")
    assert embedder.is_semantic is False
    assert embedder.load_error == "model_file_not_found"


def test_falls_back_when_model_file_does_not_exist() -> None:
    embedder = LocalKBEmbedder(model_path="/nonexistent/model.gguf")
    assert embedder.is_semantic is False
    assert embedder.load_error == "model_file_not_found"


def test_fallback_embed_is_deterministic_and_dimension_stable() -> None:
    embedder = LocalKBEmbedder(model_path="")
    first = embedder.embed(["hello world"])
    second = embedder.embed(["hello world"])
    assert first == second
    assert len(first[0]) == embedder.dimensions


def test_empty_texts_returns_empty_list() -> None:
    embedder = LocalKBEmbedder(model_path="")
    assert embedder.embed([]) == []

"""M7.7 Slice 1 — local embedder: real path when available, honest fallback."""
from __future__ import annotations

from factory.memory.runtime.embedding_local import LlamaCppEmbedder


def test_falls_back_when_no_model_path_configured() -> None:
    embedder = LlamaCppEmbedder(model_path="")
    assert embedder.is_semantic is False
    assert embedder.load_error == "model_file_not_found"


def test_falls_back_when_model_file_does_not_exist() -> None:
    embedder = LlamaCppEmbedder(model_path="/nonexistent/model.gguf")
    assert embedder.is_semantic is False
    assert embedder.load_error == "model_file_not_found"


def test_fallback_embed_is_deterministic_and_dimension_stable() -> None:
    embedder = LlamaCppEmbedder(model_path="")
    first = embedder.embed(["hello world"])
    second = embedder.embed(["hello world"])
    assert first == second
    assert len(first[0]) == embedder.dimensions


def test_fallback_embed_distinguishes_different_content() -> None:
    embedder = LlamaCppEmbedder(model_path="")
    [a], [b] = embedder.embed(["dark mode preference"]), embedder.embed(["completely different topic"])
    assert a != b


def test_empty_texts_returns_empty_list() -> None:
    embedder = LlamaCppEmbedder(model_path="")
    assert embedder.embed([]) == []


def test_fallback_vector_of_empty_string_is_all_zero() -> None:
    embedder = LlamaCppEmbedder(model_path="")
    [vector] = embedder.embed([""])
    assert all(v == 0.0 for v in vector)

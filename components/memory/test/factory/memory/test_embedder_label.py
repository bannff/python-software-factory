from __future__ import annotations

from factory.memory.runtime.embedding import LLMGatewayEmbedder
from factory.llm_gateway.runtime.adapters.ollama_adapter import OllamaEmbedder


def test_label_reports_the_ollama_embedders_real_model(monkeypatch) -> None:
    monkeypatch.setenv("FACTORY_LLM_EMBEDDING_ADAPTER", "ollama")
    embedder = LLMGatewayEmbedder()
    embedder._provider = OllamaEmbedder()
    assert embedder.label == "ollama/nomic-embed-text"


def test_an_explicit_model_wins_and_a_broken_provider_does_not_raise(monkeypatch) -> None:
    monkeypatch.delenv("FACTORY_LLM_EMBEDDING_ADAPTER", raising=False)
    assert LLMGatewayEmbedder(backend="ollama", model="mxbai-embed-large").label == "ollama/mxbai-embed-large"
    broken = LLMGatewayEmbedder()
    monkeypatch.setattr(LLMGatewayEmbedder, "_get_provider", lambda self: (_ for _ in ()).throw(RuntimeError("x")))
    assert broken.label == "gateway default/default model"

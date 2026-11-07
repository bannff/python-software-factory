"""P1 item 14 (owner smoke #2, 18:35): memory evolution must resolve the SAME
chat profile the agent uses (COMPANION_X_CHAT_MODEL), never a hardcoded Bedrock
default that silently requires AWS credentials on an OpenRouter-configured
deployment.
"""
from __future__ import annotations

import pytest


def test_get_llm_complete_resolves_openrouter_when_configured_for_it(monkeypatch):
    from factory.memory.server import _get_llm_complete

    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")

    captured: dict[str, object] = {}

    def fake_build(model_id: str):
        captured["model_id"] = model_id
        return lambda prompt: "ok"

    monkeypatch.setattr(
        "factory.memory.runtime.adapters.langchain_completion.build_langchain_complete",
        fake_build,
    )
    complete = _get_llm_complete()
    assert complete is not None
    assert complete("hello") == "ok"
    assert captured["model_id"] == "openrouter"


def test_get_llm_complete_never_touches_bedrock_llm_runtime_by_default(monkeypatch):
    """The old code path called LLMRuntime().get_provider(), whose default is
    bedrock regardless of what the product is configured for. Assert the new
    path never imports/constructs that runtime at all."""
    import sys

    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")

    called = {"llm_runtime_constructed": False}
    if "factory.llm_gateway.runtime.runtime" in sys.modules:
        original_init = sys.modules["factory.llm_gateway.runtime.runtime"].LLMRuntime.__init__

        def spy_init(self, *args, **kwargs):
            called["llm_runtime_constructed"] = True
            return original_init(self, *args, **kwargs)

        monkeypatch.setattr(
            "factory.llm_gateway.runtime.runtime.LLMRuntime.__init__", spy_init,
        )

    from factory.memory.server import _get_llm_complete

    monkeypatch.setattr(
        "factory.memory.runtime.adapters.langchain_completion.build_langchain_complete",
        lambda model_id: lambda prompt: "ok",
    )
    _get_llm_complete()
    assert called["llm_runtime_constructed"] is False


def test_get_llm_complete_degrades_to_none_on_unresolvable_profile(monkeypatch):
    """Never let a missing/misconfigured profile raise into the caller —
    _neo4j_runtime() must still construct successfully with evolution simply
    disabled."""
    from factory.memory.server import _get_llm_complete

    monkeypatch.delenv("COMPANION_X_CHAT_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")

    assert _get_llm_complete() is None

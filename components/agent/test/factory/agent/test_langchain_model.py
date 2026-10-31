"""Tests for framework-native chat model construction."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest

from factory.agent.runtime.adapters.langchain_model import build_langchain_chat_model


class _FakeChatOpenAI:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def _install_fake_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        sys.modules,
        "langchain_openai",
        SimpleNamespace(ChatOpenAI=_FakeChatOpenAI),
    )


def test_openrouter_builds_native_chat_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_openai(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://companion.example")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Companion-X")

    model = build_langchain_chat_model("openrouter/deepseek/deepseek-chat")

    assert isinstance(model, _FakeChatOpenAI)
    assert model.kwargs == {
        "model": "deepseek/deepseek-chat",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "test-secret",
        "default_headers": {
            "HTTP-Referer": "https://companion.example",
            "X-Title": "Companion-X",
        },
        "max_retries": 2,
    }


def test_openrouter_missing_key_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_openai(monkeypatch)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY is required"):
        build_langchain_chat_model("openrouter/openai/gpt-4o")


class _FakeChatOllama:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeChatBedrockConverse:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_ollama_factory_preserves_native_model_and_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        sys.modules,
        "langchain_ollama",
        SimpleNamespace(ChatOllama=_FakeChatOllama),
    )
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:22434")

    model = build_langchain_chat_model("ollama/llama3.2")

    assert isinstance(model, _FakeChatOllama)
    assert model.kwargs == {
        "model": "llama3.2",
        "base_url": "http://localhost:22434",
    }


def test_bedrock_factory_preserves_model_region_and_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from factory.agent.runtime.adapters import aws_creds

    fake_client = object()
    fake_session = SimpleNamespace(client=lambda *args, **kwargs: fake_client)
    monkeypatch.setattr(aws_creds, "get_refreshable_session", lambda: fake_session)
    monkeypatch.setitem(
        sys.modules,
        "langchain_aws",
        SimpleNamespace(ChatBedrockConverse=_FakeChatBedrockConverse),
    )
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COMPANION_X_CHAT_THINKING_BUDGET", "2048")

    model = build_langchain_chat_model("us.anthropic.claude-sonnet-4-6")

    assert isinstance(model, _FakeChatBedrockConverse)
    assert model.kwargs == {
        "model": "us.anthropic.claude-sonnet-4-6",
        "region_name": "us-west-2",
        "client": fake_client,
        "additional_model_request_fields": {
            "thinking": {"type": "enabled", "budget_tokens": 2048},
        },
    }


def _configure_compat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_PROFILES", "lm-studio")
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("LM_STUDIO_API_KEY", "compat-secret")
    monkeypatch.setenv("LM_STUDIO_MODEL", "local-model")


def test_openai_compat_builds_native_chat_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_openai(monkeypatch)
    _configure_compat(monkeypatch)

    model = build_langchain_chat_model("openai-compat/lm-studio")

    assert isinstance(model, _FakeChatOpenAI)
    assert model.kwargs == {
        "model": "local-model",
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key": "compat-secret",
        "default_headers": {},
        "max_retries": 2,
    }


def test_openai_compat_carries_the_generated_session_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from factory.llm_gateway.runtime.openai_compat_policy import session_token

    _install_fake_openai(monkeypatch)
    _configure_compat(monkeypatch)
    monkeypatch.setenv("LM_STUDIO_SESSION_HEADER", "x-lm-studio-session")

    model = build_langchain_chat_model("openai-compat/lm-studio")

    # Aux scope (no session_id): one deployment-wide token, never omitted.
    assert model.kwargs["default_headers"] == {
        "x-lm-studio-session": session_token(""),
    }


def test_openai_compat_never_falls_through_to_bedrock(monkeypatch) -> None:
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_PROFILES", "missing")
    monkeypatch.setitem(
        sys.modules,
        "langchain_aws",
        SimpleNamespace(ChatBedrockConverse=lambda **_: pytest.fail("Bedrock constructed")),
    )

    with pytest.raises(ValueError, match="chat profile unavailable"):
        build_langchain_chat_model("openai-compat/missing")

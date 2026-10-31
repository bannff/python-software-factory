"""Tests for the side-chat completion builder (feature-map row 19).

Pins what issue #41 exposed on this path: the builder must build the exact
model id its caller resolved (the gateway wiring resolves
``COMPANION_X_CHAT_MODEL``, the same model the rest of Companion-X uses) for
every configured provider shape, and failures must name the configuration to
fix instead of raising something the wiring can only swallow.
"""
from __future__ import annotations

import pytest

from factory.mcp_utils.runtime.side_llm_complete import build_mcp_utils_complete


class _FakeModel:
    """Records constructor kwargs in place of a real LangChain chat model."""

    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs: object) -> None:
        type(self).calls.append(kwargs)

    def invoke(self, prompt: str):
        class _Reply:
            content = "answered"

        return _Reply()


@pytest.fixture(autouse=True)
def _reset_fake_calls() -> None:
    _FakeModel.calls.clear()


def test_bedrock_model_is_built_from_the_environment_region(monkeypatch):
    """The builder must not invent a region: ``ChatProfile`` carries none."""
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setattr("langchain_aws.ChatBedrockConverse", _FakeModel)

    complete = build_mcp_utils_complete("us.anthropic.claude-sonnet-4-6")

    assert _FakeModel.calls == [
        {"model": "us.anthropic.claude-sonnet-4-6", "region_name": "eu-west-1"},
    ]
    assert complete("how much is stored?") == "answered"


def test_openrouter_profile_without_api_key_names_the_variable(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        build_mcp_utils_complete("openrouter")


def test_openrouter_model_is_built_from_the_resolved_profile(monkeypatch):
    """The OpenAI-shaped branch must build from fields ``ChatProfile`` actually
    has — a stale field name degraded this path to an AttributeError."""
    monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-real-key")
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("OPENROUTER_HTTP_REFERER", raising=False)
    monkeypatch.delenv("OPENROUTER_APP_TITLE", raising=False)
    monkeypatch.delenv("OPENROUTER_MAX_RETRIES", raising=False)
    monkeypatch.setattr("langchain_openai.ChatOpenAI", _FakeModel)

    build_mcp_utils_complete("openrouter")

    assert _FakeModel.calls == [{
        "model": "deepseek/deepseek-v4-flash",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "not-a-real-key",
        "default_headers": {},
        "max_retries": 2,
    }]


def test_configured_openai_compat_profile_is_built_for_side_turns(monkeypatch):
    """A named OpenAI-compatible profile is a selectable chat model, so the
    side panel must plan on it too — not fail as an unsupported provider."""
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_PROFILES", "lm-studio")
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("LM_STUDIO_API_KEY", "not-a-real-key")
    monkeypatch.setenv("LM_STUDIO_MODEL", "local-model")
    monkeypatch.setattr("langchain_openai.ChatOpenAI", _FakeModel)

    build_mcp_utils_complete("openai-compat/lm-studio")

    assert _FakeModel.calls == [{
        "model": "local-model",
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key": "not-a-real-key",
        "default_headers": {},
        "max_retries": 2,
    }]

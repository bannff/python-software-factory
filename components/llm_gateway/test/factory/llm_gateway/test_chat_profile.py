"""Contract tests for safe provider-neutral chat profile resolution."""

from __future__ import annotations

import pytest

from factory.llm_gateway.interface import configured_chat_model_id, resolve_chat_profile


def test_openrouter_profile_preserves_vendor_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("OPENROUTER_MAX_RETRIES", raising=False)

    profile = resolve_chat_profile("openrouter/deepseek/deepseek-chat")

    assert profile.provider == "openrouter"
    assert profile.model == "deepseek/deepseek-chat"
    assert profile.base_url == "https://openrouter.ai/api/v1"
    assert profile.api_key_env == "OPENROUTER_API_KEY"
    assert profile.max_retries == 2


def test_openrouter_profile_never_contains_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "not-for-profile-output"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)

    profile = resolve_chat_profile("openrouter/openai/gpt-4o")

    assert secret not in repr(profile)
    assert profile.api_key_env == "OPENROUTER_API_KEY"


def test_openrouter_profile_reads_safe_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://router.example/v1")
    monkeypatch.setenv("OPENROUTER_MAX_RETRIES", "4")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://companion.example")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Companion-X")

    profile = resolve_chat_profile("openrouter/anthropic/claude-sonnet-4")

    assert profile.base_url == "https://router.example/v1"
    assert profile.max_retries == 4
    assert profile.default_headers == {
        "HTTP-Referer": "https://companion.example",
        "X-Title": "Companion-X",
    }


def test_ollama_profile_preserves_existing_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    profile = resolve_chat_profile("ollama/llama3.2")

    assert profile.provider == "ollama"
    assert profile.model == "llama3.2"
    assert profile.base_url == "http://localhost:11434"
    assert profile.api_key_env is None


def test_bedrock_profile_preserves_bare_model_id() -> None:
    model_id = "us.anthropic.claude-sonnet-4-6"

    profile = resolve_chat_profile(model_id)

    assert profile.provider == "bedrock"
    assert profile.model == model_id
    assert profile.base_url is None
    assert profile.api_key_env is None


@pytest.mark.parametrize("model_id", ["", "openrouter/", "ollama/"])
def test_profile_rejects_missing_native_model(model_id: str) -> None:
    with pytest.raises(ValueError, match="model"):
        resolve_chat_profile(model_id)


def test_openrouter_profile_serialization_excludes_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    from dataclasses import asdict

    secret = "must-not-serialize"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)

    serialized = json.dumps(asdict(
        resolve_chat_profile("openrouter/openai/gpt-4o"),
    ))

    assert secret not in serialized
    assert "OPENROUTER_API_KEY" in serialized


def test_openrouter_provider_uses_configured_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")

    profile = resolve_chat_profile("openrouter")

    assert profile.provider == "openrouter"
    assert profile.model == "deepseek/deepseek-v4-flash"


def test_openrouter_provider_requires_configured_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    with pytest.raises(ValueError, match="OPENROUTER_MODEL"):
        resolve_chat_profile("openrouter")


def test_configured_chat_model_id_reads_the_chat_model_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one read of the deployment's chat model selector, so ambient
    consumers (side-chat planning) cannot hand-maintain a divergent default."""
    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", "  us.anthropic.claude-sonnet-4-6  ")
    assert configured_chat_model_id() == "us.anthropic.claude-sonnet-4-6"

    monkeypatch.delenv("COMPANION_X_CHAT_MODEL", raising=False)
    assert configured_chat_model_id() == ""

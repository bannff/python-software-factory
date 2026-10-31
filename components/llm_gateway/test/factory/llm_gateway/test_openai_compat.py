"""Security and catalog tests for named OpenAI-compatible profiles."""
from __future__ import annotations

import json
from dataclasses import asdict

import pytest
from hypothesis import given, strategies as st

from factory.llm_gateway.interface import list_chat_models, resolve_chat_profile
from factory.llm_gateway.runtime.openai_compat_policy import (
    SAFE_PROFILE_ERROR, credential_clean_profile_name, profile_env_stem,
    validate_base_url,
)


def configure(monkeypatch: pytest.MonkeyPatch, name: str = "lm-studio") -> None:
    stem = name.upper().replace("-", "_")
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_PROFILES", name)
    monkeypatch.setenv(f"{stem}_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv(f"{stem}_API_KEY", "sentinel-secret")
    monkeypatch.setenv(f"{stem}_MODEL", "local-model")


def test_profile_is_allowlisted_secret_free_and_provider_explicit(monkeypatch) -> None:
    configure(monkeypatch)
    profile = resolve_chat_profile("openai-compat/lm-studio")
    assert profile.provider == "openai-compat"
    assert profile.model == "local-model"
    assert profile.base_url == "http://127.0.0.1:1234/v1"
    assert profile.api_key_env == "LM_STUDIO_API_KEY"
    assert "sentinel-secret" not in repr(profile)
    assert "sentinel-secret" not in json.dumps(asdict(profile))


def test_allowlist_is_checked_before_environment_and_errors_are_identical(monkeypatch) -> None:
    monkeypatch.setenv("SHADOW_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("SHADOW_API_KEY", "present-secret")
    monkeypatch.setenv("SHADOW_MODEL", "present-model")
    with pytest.raises(ValueError) as present:
        resolve_chat_profile("openai-compat/shadow")
    monkeypatch.delenv("SHADOW_BASE_URL")
    monkeypatch.delenv("SHADOW_API_KEY")
    monkeypatch.delenv("SHADOW_MODEL")
    with pytest.raises(ValueError) as absent:
        resolve_chat_profile("openai-compat/shadow")
    assert str(present.value) == str(absent.value) == SAFE_PROFILE_ERROR


def test_missing_config_and_credential_shaped_name_fail_safely(monkeypatch) -> None:
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_PROFILES", "missing")
    with pytest.raises(ValueError, match=SAFE_PROFILE_ERROR):
        resolve_chat_profile("openai-compat/missing")
    shaped = "ghp_" + "a" * 20
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_PROFILES", shaped)
    with pytest.raises(ValueError, match=SAFE_PROFILE_ERROR):
        resolve_chat_profile(f"openai-compat/{shaped}")


@pytest.mark.parametrize("url", [
    "http://example.com/v1", "ftp://127.0.0.1/v1",
    "https://user@example.com/v1", "https://example.com/v1?token=x",
    "https://example.com/v1#fragment",
])
def test_base_url_policy_rejects_unsafe_shapes(monkeypatch, url: str) -> None:
    monkeypatch.delenv("COMPANION_X_OPENAI_COMPAT_REMOTE_ORIGINS", raising=False)
    with pytest.raises(ValueError, match=SAFE_PROFILE_ERROR):
        validate_base_url(url)


def test_remote_https_requires_exact_operator_origin(monkeypatch) -> None:
    monkeypatch.setenv(
        "COMPANION_X_OPENAI_COMPAT_REMOTE_ORIGINS", "https://models.example:8443",
    )
    assert validate_base_url("https://models.example:8443/v1") == (
        "https://models.example:8443/v1"
    )
    with pytest.raises(ValueError, match=SAFE_PROFILE_ERROR):
        validate_base_url("https://other.example:8443/v1")


def test_catalog_contains_no_endpoint_or_credential_metadata(monkeypatch) -> None:
    configure(monkeypatch)
    monkeypatch.delenv("COMPANION_X_CHAT_MODEL", raising=False)
    catalog = list_chat_models().models
    assert [item.model_id for item in catalog] == ["openai-compat/lm-studio"]
    serialized = repr(catalog)
    assert "sentinel-secret" not in serialized
    assert "127.0.0.1" not in serialized
    assert "API_KEY" not in serialized


def test_empty_catalog_is_truthfully_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("COMPANION_X_CHAT_MODEL", raising=False)
    monkeypatch.delenv("COMPANION_X_OPENAI_COMPAT_PROFILES", raising=False)
    with pytest.raises(ValueError, match="catalog unavailable"):
        list_chat_models()


def test_failure_text_and_traceback_exclude_secret(monkeypatch) -> None:
    import traceback

    configure(monkeypatch)
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "https://user:sentinel-secret@example.com/v1")
    with pytest.raises(ValueError) as failure:
        resolve_chat_profile("openai-compat/lm-studio")
    rendered = "".join(traceback.format_exception(failure.value))
    assert str(failure.value) == SAFE_PROFILE_ERROR
    assert "sentinel-secret" not in rendered


_valid_names = st.from_regex(
    r"[a-z][a-z0-9-]{0,30}[a-z0-9]", fullmatch=True,
).filter(credential_clean_profile_name)


@given(_valid_names)
def test_profile_stem_is_deterministic(name: str) -> None:
    assert profile_env_stem(name) == name.upper().replace("-", "_")

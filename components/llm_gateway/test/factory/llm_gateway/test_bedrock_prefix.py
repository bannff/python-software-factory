"""Behavioral pin: bedrock is one registry option, not a default epilogue.

Epic #124 S3 — the deployed selector (``COMPANION_X_CHAT_MODEL=us.anthropic.
claude-sonnet-4-6``) MUST keep resolving provider=bedrock pre/post the PR,
and the explicit ``bedrock/`` registry spelling must resolve to the exact
same profile.
"""
from __future__ import annotations

import pytest

from factory.llm_gateway.interface import configured_chat_model_id, resolve_chat_profile


_DEPLOYED_SELECTOR = "us.anthropic.claude-sonnet-4-6"


def test_deployed_selector_still_resolves_provider_bedrock(monkeypatch) -> None:
    """Behavior-preserving guard: unset anything provider-ish, the bare
    deployed model id resolves to bedrock (the owner's stack default)."""
    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", _DEPLOYED_SELECTOR)
    assert configured_chat_model_id() == _DEPLOYED_SELECTOR

    profile = resolve_chat_profile(_DEPLOYED_SELECTOR)
    assert profile.provider == "bedrock"
    assert profile.model == _DEPLOYED_SELECTOR


def test_explicit_bedrock_prefix_resolves_the_same_profile() -> None:
    explicit = resolve_chat_profile(f"bedrock/{_DEPLOYED_SELECTOR}")
    bare = resolve_chat_profile(_DEPLOYED_SELECTOR)

    assert explicit.provider == "bedrock"
    assert explicit.model == _DEPLOYED_SELECTOR
    assert explicit.model.startswith(_DEPLOYED_SELECTOR)


def test_bedrock_prefix_without_a_model_id_is_a_named_no_go() -> None:
    with pytest.raises(ValueError, match="bedrock/"):
        resolve_chat_profile("bedrock/")

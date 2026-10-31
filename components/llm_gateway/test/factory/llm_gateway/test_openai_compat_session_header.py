"""OpenCode-go session header: name validation, deterministic token, merge.

The provider rejects a chat request with 400 MissingSessionID unless a
per-profile session header rides every request; the value must be stable
across restarts (routing/prompt-cache affinity) and never derived from a
secret. See ``openai_compat_policy.resolve_session_header`` for the rules.
"""
from __future__ import annotations

import pytest

from factory.llm_gateway.interface import resolve_chat_profile
from factory.llm_gateway.runtime.openai_compat_policy import (
    SAFE_PROFILE_ERROR, session_token,
)

_PROFILE = "opencode"


def _configure(monkeypatch: pytest.MonkeyPatch, header: str | None) -> None:
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_PROFILES", _PROFILE)
    monkeypatch.setenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1")
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_REMOTE_ORIGINS", "https://opencode.ai")
    monkeypatch.setenv("OPENCODE_API_KEY", "session-secret")
    monkeypatch.setenv("OPENCODE_MODEL", "deepseek-v4.1-flash")
    if header is None:
        monkeypatch.delenv("OPENCODE_SESSION_HEADER", raising=False)
    else:
        monkeypatch.setenv("OPENCODE_SESSION_HEADER", header)


@pytest.mark.parametrize("header", [
    # credential headers
    "Authorization", "authorization", "X-API-Key", "x-auth-token", "x-access-token",
    # proxy family
    "Proxy-Authorization", "proxy-authorization",
    # protocol headers
    "Host", "Cookie",
    # otherwise-invalid names
    "x-session\r\nInjected: 1", "x-" + "a" * 32, "session-id",
    "x-", "X-Session",
])
def test_malformed_or_reserved_session_header_is_rejected_fail_closed(
    monkeypatch: pytest.MonkeyPatch, header: str,
) -> None:
    _configure(monkeypatch, header)

    with pytest.raises(ValueError) as failure:
        resolve_chat_profile(f"openai-compat/{_PROFILE}")

    assert str(failure.value) == SAFE_PROFILE_ERROR


def test_absent_session_header_leaves_the_profile_headerless(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, None)

    profile = resolve_chat_profile(f"openai-compat/{_PROFILE}")

    assert profile.session_header is None
    assert profile.headers_for("thread-1") == {}


def test_configured_session_header_is_exposed_name_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, "x-opencode-session")

    profile = resolve_chat_profile(f"openai-compat/{_PROFILE}")

    assert profile.session_header == "x-opencode-session"
    # The profile is credential-free by construction: no value is ever stored.
    assert "x-opencode-session" not in profile.headers_for("thread-1").values()
    assert "session-secret" not in repr(profile)


def test_session_token_is_stable_identical_per_scope() -> None:
    assert session_token("thread-42") == session_token("thread-42")


def test_session_token_is_distinct_across_scopes() -> None:
    assert session_token("thread-42") != session_token("thread-43")


def test_session_token_shape_is_fixed_width_opaque() -> None:
    token = session_token("thread-42")

    assert token.startswith("ses_")
    assert len(token) == len("ses_") + 32
    assert all(char in "0123456789abcdef" for char in token.removeprefix("ses_"))


def test_session_token_never_leaks_the_raw_scope() -> None:
    assert "thread-42" not in session_token("thread-42")


def test_session_token_of_empty_scope_is_the_shared_aux_scope() -> None:
    """Aux paths (title/summary/side-chat/memory) omit the scope; theirs is one
    deployment-wide token, distinct from any conversation's."""
    assert session_token("") == session_token("")
    assert session_token("") != session_token("thread-42")


def test_headers_for_merges_declared_headers_with_generated_session_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, "x-opencode-session")
    profile = resolve_chat_profile(f"openai-compat/{_PROFILE}")

    headers = profile.headers_for("thread-42")

    assert headers == {"x-opencode-session": session_token("thread-42")}


def test_headers_for_does_not_mutate_the_declared_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, "x-opencode-session")
    profile = resolve_chat_profile(f"openai-compat/{_PROFILE}")

    profile.headers_for("thread-42")

    assert profile.default_headers == {}

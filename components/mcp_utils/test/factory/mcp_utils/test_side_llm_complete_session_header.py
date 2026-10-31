"""The side-chat planner must carry the openai-compat session header.

``side_llm_complete.py`` (mcp_utils) is the fourth profile→client builder an
openai-compat profile (e.g. opencode-go) routes through; if it drops
``headers_for()`` every side-panel planner turn 400s with MissingSessionID and
the side panel silently degrades to "no tools". This pins the header so a
revert cannot ship undetected.
"""
from __future__ import annotations

import pytest

from factory.llm_gateway.runtime.openai_compat_policy import session_token
from factory.mcp_utils.runtime.side_llm_complete import build_mcp_utils_complete

_HEADER = "x-opencode-session"


class _FakeChatOpenAI:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs: object) -> None:
        type(self).calls.append(kwargs)

    def invoke(self, prompt: str):
        class _Reply:
            content = "planned"

        return _Reply()


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeChatOpenAI.calls.clear()
    monkeypatch.setattr("langchain_openai.ChatOpenAI", _FakeChatOpenAI)


def _configure(monkeypatch: pytest.MonkeyPatch, header: str | None) -> None:
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_PROFILES", "opencode")
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_REMOTE_ORIGINS", "https://opencode.ai")
    monkeypatch.setenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1")
    monkeypatch.setenv("OPENCODE_API_KEY", "side-secret")
    monkeypatch.setenv("OPENCODE_MODEL", "deepseek-v4.1-flash")
    if header is None:
        monkeypatch.delenv("OPENCODE_SESSION_HEADER", raising=False)
    else:
        monkeypatch.setenv("OPENCODE_SESSION_HEADER", header)


def test_compat_side_planner_carries_the_generated_session_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, _HEADER)

    build_mcp_utils_complete("openai-compat/opencode")

    # Aux scope: no session id → one deployment-wide token, never omitted.
    assert _FakeChatOpenAI.calls[0]["default_headers"] == {
        _HEADER: session_token(""),
    }


def test_compat_side_planner_without_session_header_passes_an_empty_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, None)

    build_mcp_utils_complete("openai-compat/opencode")

    assert _FakeChatOpenAI.calls[0]["default_headers"] == {}

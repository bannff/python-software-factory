"""Integration test for the live side-chat gateway wiring (feature-map row 19).

Proves ``register_side_chat`` composes a real SideChatService and mounts it
at the real HTTP paths, end-to-end through FastAPI's TestClient (which runs
sync endpoints in a worker thread — the same shape production requests take).
The aggregator + category lookup are faked (no live MCP server needed); the
LangChain chat model is faked too (a real Bedrock/OpenRouter client needs live
credentials), so these tests pin exactly what issue #41 got wrong: which model
id the planner resolves, whether it really plans, and what a boot with no
usable model says about it.
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.runtime.side_chat_wiring import register_side_chat, side_chat_status

_WIRING_LOGGER = "factory.api.runtime.side_chat_wiring"
_CONFIGURED_MODEL = "us.anthropic.claude-sonnet-4-6"


class _FakeAggregator:
    def invoke_tool(self, tool_name: str, **kwargs):
        return {"tool": tool_name, "kwargs": kwargs}


class _FakeChatModel:
    """Stands in for a real LangChain chat model, recording its constructor."""

    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs: object) -> None:
        type(self).calls.append(kwargs)

    def invoke(self, prompt: str):
        class _Reply:
            content = json.dumps([{"tool": "memory_stats", "args": {}}])

        return _Reply()


@pytest.fixture(autouse=True)
def _clean_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No ambient chat config — every test states the model it wants."""
    for name in (
        "SIDE_CHAT_MODEL_ID", "COMPANION_X_CHAT_MODEL",
        "OPENROUTER_MODEL", "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    _FakeChatModel.calls.clear()


@contextmanager
def _wired_client():
    app = FastAPI()
    with patch(
        "factory.api.runtime.bridge._get_aggregator", return_value=_FakeAggregator(),
    ), patch(
        "factory.mcp_server.runtime.category_lookup.build_category_lookup",
        return_value={"memory_stats": "deterministic"},
    ), patch(
        "langchain_aws.ChatBedrockConverse", _FakeChatModel,
    ):
        register_side_chat(app)
        yield TestClient(app)


def _planner_warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == _WIRING_LOGGER]


def test_open_close_work_over_the_real_wiring():
    with _wired_client() as client:
        r = client.post("/api/chat/slots/wired-slot/side/open")
        assert r.status_code == 200
        assert r.json() == {"slot": "wired-slot", "turns": []}
        assert client.post("/api/chat/slots/wired-slot/side/close").json() == {"closed": True}


def test_turn_degrades_to_no_tools_without_a_configured_model():
    """No chat model configured in the test environment -> planner build fails
    -> register_side_chat installs the empty-plan fallback -> the endpoint
    still answers 200 (never 500), just with no tool calls run."""
    with _wired_client() as client:
        client.post("/api/chat/slots/s/side/open")
        r = client.post("/api/chat/slots/s/side/turn", json={"query": "anything"})
        assert r.status_code == 200
        body = r.json()
        assert body["refused"] == []
        assert len(body["turns"]) == 1  # just the recorded user turn


def test_configured_chat_model_builds_a_working_planner(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
):
    """Issue #41: the side panel plans with ``COMPANION_X_CHAT_MODEL`` — the
    same model the rest of Companion-X resolves — so boot is warning-free and
    the planner really runs a tool, not the empty fallback."""
    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", _CONFIGURED_MODEL)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

    with caplog.at_level(logging.WARNING), _wired_client() as client:
        assert _FakeChatModel.calls[-1] == {
            "model": _CONFIGURED_MODEL, "region_name": "eu-west-1",
        }
        assert side_chat_status() == {"status": "ready", "model_id": _CONFIGURED_MODEL}
        assert _planner_warnings(caplog) == []

        client.post("/api/chat/slots/s/side/open")
        body = client.post(
            "/api/chat/slots/s/side/turn", json={"query": "how much is stored?"},
        ).json()

    assert any(
        turn["role"] == "tool" and "memory_stats" in turn["text"] for turn in body["turns"]
    ), body


def test_boot_without_a_configured_model_names_the_missing_variable(
    caplog: pytest.LogCaptureFixture,
):
    """Issue #41: one actionable log line (no traceback) names the variable,
    and the deliberate 'never fail route registration' stance is preserved."""
    with caplog.at_level(logging.WARNING), _wired_client() as client:
        (record,) = _planner_warnings(caplog)
        assert "COMPANION_X_CHAT_MODEL" in record.getMessage()
        assert record.exc_info is None
        assert side_chat_status() == {
            "status": "unavailable",
            "reason": "no chat model configured for the side panel: "
                      "set COMPANION_X_CHAT_MODEL",
        }
        assert client.post("/api/chat/slots/s/side/open").status_code == 200


def test_openrouter_selector_without_a_model_names_the_variable(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
):
    """A bare ``openrouter`` selector with no ``OPENROUTER_MODEL`` must say
    which variable is missing, not leak a blank-model traceback."""
    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", "openrouter")

    with caplog.at_level(logging.WARNING), _wired_client():
        (record,) = _planner_warnings(caplog)
        assert "OPENROUTER_MODEL" in record.getMessage()
        assert record.exc_info is None


def test_explicit_side_chat_override_wins_over_the_configured_chat_model(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", "us.anthropic.claude-sonnet-4-6")
    monkeypatch.setenv("SIDE_CHAT_MODEL_ID", "us.anthropic.claude-opus-4-1")

    with _wired_client():
        assert _FakeChatModel.calls[-1]["model"] == "us.anthropic.claude-opus-4-1"
        assert side_chat_status() == {
            "status": "ready", "model_id": "us.anthropic.claude-opus-4-1",
        }

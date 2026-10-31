"""Side-chat inherits the deployment chat profile exactly like chat turns do.

Epic #124 S3: the side panel planner must resolve the SAME gateway chat
profile (via ``resolve_chat_profile``, the single chat-resolution authority)
as the strands chat path — including the explicit ``bedrock/`` spelling —
and when AWS credentials do not resolve the no-go must surface as a typed
``AgentCredentialError`` that names the configuration to fix (visible in
``/api/health`` via side_chat_status), never as botocore's raw
``ProfileNotFound``/``AttributeError`` noise.
"""
from __future__ import annotations

import pytest
from unittest import mock

from factory.llm_gateway.interface import AgentCredentialError
from factory.mcp_utils.runtime.side_llm_complete import build_mcp_utils_complete

_DEPLOYED_SELECTOR = "us.anthropic.claude-sonnet-4-6"


class _FakeBedrockModel:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs: object) -> None:
        type(self).calls.append(kwargs)

    def invoke(self, prompt: str):
        class _Reply:
            content = "answered"

        return _Reply()


@pytest.fixture(autouse=True)
def _reset_fake_calls():
    _FakeBedrockModel.calls.clear()


def test_side_chat_inherits_the_explicit_bedrock_registry_selector(monkeypatch) -> None:
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setattr("langchain_aws.ChatBedrockConverse", _FakeBedrockModel)

    for selector in (_DEPLOYED_SELECTOR, f"bedrock/{_DEPLOYED_SELECTOR}"):
        complete = build_mcp_utils_complete(selector)
        assert complete("hi") == "answered"
        assert _FakeBedrockModel.calls[-1] == {
            "model": _DEPLOYED_SELECTOR,
            "region_name": "eu-west-1",
        }


def test_unresolved_credentials_surface_as_typed_no_go(monkeypatch) -> None:
    """Before the S3 gate this path let botocore's ProfileNotFound (or a bare
    AttributeError) surface through the side-chat planner's catch-all; the
    named no-go is now the single exception shape the wiring reports."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    err = __import__("botocore").exceptions.ProfileNotFound(profile="")

    def _no_creds(*args, **kwargs):
        raise err

    monkeypatch.setattr("langchain_aws.ChatBedrockConverse", _no_creds)

    with pytest.raises(AgentCredentialError) as excinfo:
        build_mcp_utils_complete(_DEPLOYED_SELECTOR)

    message = str(excinfo.value)
    assert "no AWS credentials resolve" in message
    assert "AWS_PROFILE" in message

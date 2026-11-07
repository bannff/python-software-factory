"""A missing chat model must surface as a typed code, not tool_execution_failed (#239)."""
from __future__ import annotations

import pytest

from factory.agent.mcp.tools import _reason
from factory.agent.runtime.adapters.provider_errors import provider_error_message
from factory.llm_gateway.interface import AgentCredentialError
from factory.mcp_utils.interface import TypedToolFailure


@pytest.mark.asyncio
async def test_credential_error_becomes_model_not_configured(monkeypatch) -> None:
    class Chat:
        async def invoke(self, *args, **kwargs):
            raise AgentCredentialError("Bedrock chat model unavailable: no AWS credentials")

    monkeypatch.setattr("factory.agent.runtime.chat.get_chat_agent", lambda: Chat())
    with pytest.raises(TypedToolFailure) as caught:
        await _reason(None, "hi", {}, {}, None)
    assert caught.value.code == "model_not_configured"
    assert "no AWS credentials" in str(caught.value)


def test_stream_path_message_names_the_missing_model() -> None:
    message = provider_error_message(AgentCredentialError("x"))
    assert "COMPANION_X_CHAT_MODEL" in message

"""Official Strands model integrations for Companion-X chat."""
from __future__ import annotations

import os
from typing import Any

from factory.llm_gateway.interface import credential_gate, resolve_chat_profile


def build_strands_model(model_id: str, session_id: str = "") -> Any:
    """Build the configured model through an official Strands integration."""
    profile = resolve_chat_profile(model_id)
    if profile.provider in ("openrouter", "openai-compat"):
        api_key = os.getenv(profile.api_key_env or "", "").strip()
        if not api_key:
            raise ValueError("chat profile unavailable")
        from openai import AsyncOpenAI

        from strands.models.openai import OpenAIModel
        # Strands OpenAIModel accepts any OpenAI-compatible client; the
        # base_url/api_key/default_headers ride the client, not the config.
        client = AsyncOpenAI(
            base_url=profile.base_url,
            api_key=api_key,
            default_headers=profile.headers_for(session_id) or None,
            max_retries=profile.max_retries,
        )
        return OpenAIModel(client=client, model_id=profile.model)
    if profile.provider == "ollama":
        from strands.models.ollama import OllamaModel
        return OllamaModel(profile.base_url, model_id=profile.model)
    from strands.models.bedrock import BedrockModel
    from .aws_creds import get_refreshable_session
    with credential_gate(profile.provider):
        kwargs: dict[str, Any] = {
            "model_id": model_id,
            "boto_session": get_refreshable_session(),
        }
        budget = os.getenv("COMPANION_X_CHAT_THINKING_BUDGET", "").strip()
        if budget:
            kwargs["additional_request_fields"] = {
                "thinking": {"type": "enabled", "budget_tokens": int(budget)},
            }
        return BedrockModel(**kwargs)


__all__ = ["build_strands_model"]

"""Official LangChain model integrations for Companion-X chat."""

from __future__ import annotations

import os
from typing import Any

from factory.llm_gateway.interface import credential_gate, resolve_chat_profile


def build_langchain_chat_model(model_id: str) -> Any:
    """Build the configured model through an official LangChain integration."""
    profile = resolve_chat_profile(model_id)
    if profile.provider == "openrouter":
        api_key = os.getenv(profile.api_key_env or "", "").strip()
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouter chat")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=profile.model,
            base_url=profile.base_url,
            api_key=api_key,
            default_headers=profile.headers_for(),
            max_retries=profile.max_retries,
        )
    if profile.provider == "openai-compat":
        api_key = os.getenv(profile.api_key_env or "", "").strip()
        if not api_key:
            raise ValueError("chat profile unavailable")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=profile.model,
            base_url=profile.base_url,
            api_key=api_key,
            default_headers=profile.headers_for(),
            max_retries=profile.max_retries,
        )
    if profile.provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=profile.model, base_url=profile.base_url)
    from langchain_aws import ChatBedrockConverse
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    from .aws_creds import get_refreshable_session
    with credential_gate(profile.provider):
        kwargs: dict[str, Any] = {
            "model": model_id,
            "region_name": region,
            "client": get_refreshable_session().client("bedrock-runtime", region_name=region),
        }
        budget = os.getenv("COMPANION_X_CHAT_THINKING_BUDGET", "").strip()
        if budget:
            kwargs["additional_model_request_fields"] = {
                "thinking": {"type": "enabled", "budget_tokens": int(budget)},
            }
        return ChatBedrockConverse(**kwargs)


__all__ = ["build_langchain_chat_model"]

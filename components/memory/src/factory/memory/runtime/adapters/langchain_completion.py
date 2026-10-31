"""Memory-owned LangChain completion callback for A-MEM content evolution.

Deliberately NOT an import of ``factory.agent``'s ``build_langchain_chat_model``
(no cross-brick imports) — this mirrors the same official-LangChain-integration
pattern using only ``llm_gateway``'s shared, credential-free ``ChatProfile``,
so memory evolution resolves the exact provider the product is configured
for (P1 item 14, owner smoke #2 18:35: A-MEM silently required AWS Bedrock
credentials via ``LLMRuntime().get_provider()``'s ``bedrock`` default, even
when the deployment is configured for OpenRouter and has no AWS creds at all).
"""
from __future__ import annotations

import os
from typing import Any, Callable

from factory.llm_gateway.interface import credential_gate, resolve_chat_profile


def build_langchain_complete(model_id: str) -> Callable[[str], str]:
    """Build a synchronous ``complete(prompt) -> str`` over an official
    LangChain chat model, resolved from the same profile chat itself uses."""
    profile = resolve_chat_profile(model_id)
    model = _build_model(profile)

    def complete(prompt: str) -> str:
        response = model.invoke(prompt)
        content = getattr(response, "content", response)
        return content if isinstance(content, str) else str(content)

    return complete


def _build_model(profile: Any) -> Any:
    if profile.provider == "openrouter":
        api_key = os.getenv(profile.api_key_env or "", "").strip()
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouter chat")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=profile.model, base_url=profile.base_url, api_key=api_key,
            default_headers=profile.headers_for(), max_retries=profile.max_retries,
        )
    if profile.provider == "openai-compat":
        api_key = os.getenv(profile.api_key_env or "", "").strip()
        if not api_key:
            raise ValueError("chat profile unavailable")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=profile.model, base_url=profile.base_url, api_key=api_key,
            default_headers=profile.headers_for(), max_retries=profile.max_retries,
        )
    if profile.provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=profile.model, base_url=profile.base_url)
    from langchain_aws import ChatBedrockConverse
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    with credential_gate(profile.provider):
        return ChatBedrockConverse(model=profile.model, region_name=region)


__all__ = ["build_langchain_complete"]

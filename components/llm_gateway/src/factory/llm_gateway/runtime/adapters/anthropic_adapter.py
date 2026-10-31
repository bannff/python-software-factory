"""Anthropic adapter for LLM Gateway.

Provides LLM completions via Anthropic API (Claude models).
"""

from __future__ import annotations

import os
import time
from typing import Any

from ..ports import (
    LLMMessage,
    LLMResponse,
    LLMHealth,
)


class AnthropicProvider:
    """Anthropic LLM provider adapter."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5-20250929",
        **kwargs: Any,
    ) -> None:
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._default_model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                raise ImportError("anthropic required: pip install anthropic")
        return self._client

    def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a text completion."""
        messages = [LLMMessage(role="user", content=prompt)]
        return self.chat(messages, model, max_tokens, temperature, **kwargs)

    def chat(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a chat completion."""
        model_id = model or self._default_model
        client = self._get_client()

        # Anthropic requires system message to be separate
        system_msg = None
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        kwargs_call: dict[str, Any] = {
            "model": model_id,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msg:
            kwargs_call["system"] = system_msg

        response = client.messages.create(**kwargs_call)

        content = response.content[0].text if response.content else ""
        usage = response.usage

        return LLMResponse(
            content=content,
            model=model_id,
            provider="anthropic",
            usage={
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
            },
            finish_reason=response.stop_reason or "stop",
        )

    async def complete_async(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        """Async completion."""
        messages = [LLMMessage(role="user", content=prompt)]
        return await self.chat_async(messages, model, max_tokens, temperature, **kwargs)

    async def chat_async(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        """Async chat completion."""
        model_id = model or self._default_model
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self._api_key)
        except ImportError:
            raise ImportError("anthropic required: pip install anthropic")

        system_msg = None
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        kwargs_call: dict[str, Any] = {
            "model": model_id,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msg:
            kwargs_call["system"] = system_msg

        response = await client.messages.create(**kwargs_call)

        content = response.content[0].text if response.content else ""
        usage = response.usage

        return LLMResponse(
            content=content,
            model=model_id,
            provider="anthropic",
            usage={
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
            },
            finish_reason=response.stop_reason or "stop",
        )

    def health_check(self) -> LLMHealth:
        """Check Anthropic connectivity."""
        start = time.perf_counter()
        try:
            self._get_client()
            latency = (time.perf_counter() - start) * 1000
            return LLMHealth(healthy=True, provider="anthropic", latency_ms=latency)
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return LLMHealth(healthy=False, provider="anthropic", latency_ms=latency, message=str(e))

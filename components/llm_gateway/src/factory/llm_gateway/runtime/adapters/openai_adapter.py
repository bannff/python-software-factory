"""OpenAI adapter for LLM Gateway."""

from __future__ import annotations

import os
import time
from typing import Any

from ..ports import LLMMessage, LLMResponse, EmbeddingResponse, LLMHealth


class OpenAIProvider:
    """OpenAI LLM provider adapter."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o",
                 base_url: str | None = None, **kwargs: Any) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._default_model, self._base_url = model, base_url
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
            except ImportError:
                raise ImportError("openai required: pip install openai")
        return self._client

    def complete(self, prompt: str, model: str | None = None, max_tokens: int = 1024,
                 temperature: float = 0.7, **kwargs: Any) -> LLMResponse:
        return self.chat([LLMMessage(role="user", content=prompt)], model, max_tokens, temperature, **kwargs)

    def chat(self, messages: list[LLMMessage], model: str | None = None, max_tokens: int = 1024,
             temperature: float = 0.7, **kwargs: Any) -> LLMResponse:
        model_id = model or self._default_model
        client = self._get_client()
        openai_messages = [{"role": m.role, "content": m.content} for m in messages]
        response = client.chat.completions.create(
            model=model_id, messages=openai_messages, max_tokens=max_tokens, temperature=temperature)
        choice, usage = response.choices[0], response.usage
        return LLMResponse(content=choice.message.content or "", model=model_id, provider="openai",
                           usage={"input_tokens": usage.prompt_tokens if usage else 0,
                                  "output_tokens": usage.completion_tokens if usage else 0},
                           finish_reason=choice.finish_reason or "stop")

    async def complete_async(self, prompt: str, model: str | None = None, max_tokens: int = 1024,
                             temperature: float = 0.7, **kwargs: Any) -> LLMResponse:
        return await self.chat_async([LLMMessage(role="user", content=prompt)], model, max_tokens, temperature, **kwargs)

    async def chat_async(self, messages: list[LLMMessage], model: str | None = None, max_tokens: int = 1024,
                         temperature: float = 0.7, **kwargs: Any) -> LLMResponse:
        model_id = model or self._default_model
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        except ImportError:
            raise ImportError("openai required: pip install openai")
        openai_messages = [{"role": m.role, "content": m.content} for m in messages]
        response = await client.chat.completions.create(
            model=model_id, messages=openai_messages, max_tokens=max_tokens, temperature=temperature)
        choice, usage = response.choices[0], response.usage
        return LLMResponse(content=choice.message.content or "", model=model_id, provider="openai",
                           usage={"input_tokens": usage.prompt_tokens if usage else 0,
                                  "output_tokens": usage.completion_tokens if usage else 0},
                           finish_reason=choice.finish_reason or "stop")

    def health_check(self) -> LLMHealth:
        start = time.perf_counter()
        try:
            client = self._get_client()
            client.models.list()
            return LLMHealth(healthy=True, provider="openai", latency_ms=(time.perf_counter() - start) * 1000)
        except Exception as e:
            return LLMHealth(healthy=False, provider="openai", latency_ms=(time.perf_counter() - start) * 1000, message=str(e))


class OpenAIEmbedder:
    """OpenAI embedding provider adapter."""

    def __init__(self, api_key: str | None = None, model: str = "text-embedding-3-small",
                 base_url: str | None = None, **kwargs: Any) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._default_model, self._base_url = model, base_url
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
            except ImportError:
                raise ImportError("openai required: pip install openai")
        return self._client

    def embed(self, texts: list[str], model: str | None = None, **kwargs: Any) -> EmbeddingResponse:
        model_id = model or self._default_model
        client = self._get_client()
        response = client.embeddings.create(model=model_id, input=texts)
        embeddings = [item.embedding for item in response.data]
        return EmbeddingResponse(embeddings=embeddings, model=model_id, provider="openai",
                                 usage={"input_tokens": response.usage.prompt_tokens if response.usage else 0})

    async def embed_async(self, texts: list[str], model: str | None = None, **kwargs: Any) -> EmbeddingResponse:
        model_id = model or self._default_model
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        except ImportError:
            raise ImportError("openai required: pip install openai")
        response = await client.embeddings.create(model=model_id, input=texts)
        embeddings = [item.embedding for item in response.data]
        return EmbeddingResponse(embeddings=embeddings, model=model_id, provider="openai",
                                 usage={"input_tokens": response.usage.prompt_tokens if response.usage else 0})

    def health_check(self) -> LLMHealth:
        start = time.perf_counter()
        try:
            self._get_client()
            return LLMHealth(healthy=True, provider="openai", latency_ms=(time.perf_counter() - start) * 1000)
        except Exception as e:
            return LLMHealth(healthy=False, provider="openai", latency_ms=(time.perf_counter() - start) * 1000, message=str(e))

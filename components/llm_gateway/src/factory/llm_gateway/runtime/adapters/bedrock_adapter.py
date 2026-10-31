"""AWS Bedrock adapter for LLM Gateway.

Caches boto3 client for performance but auto-refreshes on
ExpiredTokenException using a fresh botocore session.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from ..ports import LLMMessage, LLMResponse, EmbeddingResponse, LLMHealth

logger = logging.getLogger(__name__)


def _new_client(region: str) -> Any:
    """Create a bedrock-runtime client with a fresh botocore session."""
    import boto3
    import botocore.session
    return boto3.Session(
        botocore_session=botocore.session.Session(),
    ).client("bedrock-runtime", region_name=region)


class BedrockProvider:
    """Bedrock LLM provider adapter."""

    def __init__(self, region: str = "us-east-1",
                 model: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                 **kwargs: Any) -> None:
        self._region = region
        self._default_model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = _new_client(self._region)
        return self._client

    def complete(self, prompt: str, model: str | None = None,
                 max_tokens: int = 1024, temperature: float = 0.7,
                 **kwargs: Any) -> LLMResponse:
        return self.chat(
            [LLMMessage(role="user", content=prompt)],
            model, max_tokens, temperature, **kwargs,
        )

    def chat(self, messages: list[LLMMessage], model: str | None = None,
             max_tokens: int = 1024, temperature: float = 0.7,
             **kwargs: Any) -> LLMResponse:
        model_id = model or self._default_model
        bedrock_msgs = [
            {"role": m.role, "content": [{"text": m.content}]}
            for m in messages
        ]
        for attempt in range(2):
            try:
                resp = self._get_client().converse(
                    modelId=model_id, messages=bedrock_msgs,
                    inferenceConfig={"maxTokens": max_tokens,
                                     "temperature": temperature},
                )
                break
            except Exception as e:
                if "expired" in str(e).lower() and attempt == 0:
                    logger.info("Bedrock creds expired, refreshing")
                    self._client = _new_client(self._region)
                    continue
                raise
        output = resp.get("output", {}).get("message", {})
        content = output.get("content", [{}])[0].get("text", "")
        usage = resp.get("usage", {})
        return LLMResponse(
            content=content, model=model_id, provider="bedrock",
            usage={"input_tokens": usage.get("inputTokens", 0),
                   "output_tokens": usage.get("outputTokens", 0)},
            finish_reason=resp.get("stopReason", "stop"),
        )

    async def complete_async(self, prompt: str, model: str | None = None,
                             max_tokens: int = 1024, temperature: float = 0.7,
                             **kwargs: Any) -> LLMResponse:
        import asyncio
        return await asyncio.to_thread(
            self.complete, prompt, model, max_tokens, temperature, **kwargs,
        )

    async def chat_async(self, messages: list[LLMMessage],
                         model: str | None = None, max_tokens: int = 1024,
                         temperature: float = 0.7,
                         **kwargs: Any) -> LLMResponse:
        import asyncio
        return await asyncio.to_thread(
            self.chat, messages, model, max_tokens, temperature, **kwargs,
        )

    def health_check(self) -> LLMHealth:
        start = time.perf_counter()
        try:
            self._get_client()
            return LLMHealth(healthy=True, provider="bedrock",
                             latency_ms=(time.perf_counter() - start) * 1000)
        except Exception as e:
            return LLMHealth(healthy=False, provider="bedrock",
                             latency_ms=(time.perf_counter() - start) * 1000,
                             message=str(e))


class BedrockEmbedder:
    """Bedrock embedding provider adapter."""

    def __init__(self, region: str = "us-east-1",
                 model: str = "amazon.titan-embed-text-v2:0",
                 **kwargs: Any) -> None:
        self._region = region
        self._default_model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = _new_client(self._region)
        return self._client

    def embed(self, texts: list[str], model: str | None = None,
              **kwargs: Any) -> EmbeddingResponse:
        model_id = model or self._default_model
        embeddings: list[list[float]] = []
        total_tokens = 0
        for i, text in enumerate(texts):
            body = json.dumps({"inputText": text})
            for attempt in range(2):
                try:
                    resp = self._get_client().invoke_model(
                        modelId=model_id, body=body,
                    )
                    break
                except Exception as e:
                    if "expired" in str(e).lower() and attempt == 0:
                        logger.info("Bedrock embed creds expired, refreshing")
                        self._client = _new_client(self._region)
                        continue
                    raise
            result = json.loads(resp["body"].read())
            embeddings.append(result.get("embedding", []))
            total_tokens += result.get("inputTextTokenCount", 0)
        return EmbeddingResponse(
            embeddings=embeddings, model=model_id, provider="bedrock",
            usage={"input_tokens": total_tokens},
        )

    async def embed_async(self, texts: list[str], model: str | None = None,
                          **kwargs: Any) -> EmbeddingResponse:
        import asyncio
        return await asyncio.to_thread(self.embed, texts, model, **kwargs)

    def health_check(self) -> LLMHealth:
        start = time.perf_counter()
        try:
            self._get_client()
            return LLMHealth(healthy=True, provider="bedrock",
                             latency_ms=(time.perf_counter() - start) * 1000)
        except Exception as e:
            return LLMHealth(healthy=False, provider="bedrock",
                             latency_ms=(time.perf_counter() - start) * 1000,
                             message=str(e))

"""Bound CompletionPort adapter routed through the llm_gateway brick.

Replaces the deprecated ``llm_gateway_config`` adapter: instead of building
a LiteLLM config dict for an external package, this adapter binds a
backend/model selection to a ``CompletionPort`` that native generation
stages call directly. Traffic routes through ``llm_gateway`` providers.

Retry mirrors the Strands SDK primitive
``strands.event_loop._retry.ModelRetryStrategy`` (max attempts + exponential
backoff with a delay ceiling). The Strands primitive is model-loop-scoped
and cannot be attached to a bare llm_gateway provider call, so its semantics
are reproduced here — documented SDK gap per the SDK-first tenet.
"""

from __future__ import annotations

import logging
import time

from factory.llm_gateway.interface import LLMMessage, LLMProvider, LLMRuntime

logger = logging.getLogger(__name__)


class LLMGatewayCompletionAdapter:
    """CompletionPort bound to one llm_gateway backend/model selection."""

    _DEFAULT_MODELS: dict[str, str] = {
        "ollama": "llama3.2",
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-5-20250929",
        "bedrock": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    }

    _INITIAL_DELAY_S = 1.0
    _MAX_DELAY_S = 30.0

    def __init__(
        self,
        backend: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        num_retries: int = 2,
        runtime: LLMRuntime | None = None,
    ) -> None:
        self._runtime = runtime or LLMRuntime()
        if backend not in self._runtime.available_backends():
            raise ValueError(
                f"Unsupported LLM backend '{backend}'. "
                f"Available: {self.available_backends}"
            )
        resolved_model = model or self._DEFAULT_MODELS.get(backend, "")
        if not resolved_model:
            raise ValueError(f"No default model for backend '{backend}'")
        self.backend = backend
        self.model_id = resolved_model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_attempts = max(1, int(num_retries) + 1)
        self._provider: LLMProvider | None = None

    @property
    def available_backends(self) -> list[str]:
        return sorted(self._runtime.available_backends())

    def get_completion(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Run one chat completion; per-call values override bound defaults."""
        messages: list[LLMMessage] = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))

        kwargs: dict[str, float | int] = {}
        resolved_temperature = temperature if temperature is not None else self._temperature
        if resolved_temperature is not None:
            kwargs["temperature"] = resolved_temperature
        resolved_max_tokens = max_tokens if max_tokens is not None else self._max_tokens
        if resolved_max_tokens is not None:
            kwargs["max_tokens"] = resolved_max_tokens

        provider = self._get_provider()
        delay = self._INITIAL_DELAY_S
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = provider.chat(messages, model=self.model_id, **kwargs)
                return response.content
            except Exception as error:  # transient provider failures
                last_error = error
                if attempt == self._max_attempts:
                    break
                logger.warning(
                    "Completion attempt %s/%s failed for %s/%s: %s",
                    attempt, self._max_attempts, self.backend, self.model_id, error,
                )
                time.sleep(delay)
                delay = min(delay * 2, self._MAX_DELAY_S)
        raise RuntimeError(
            f"Completion failed after {self._max_attempts} attempts "
            f"({self.backend}/{self.model_id})"
        ) from last_error

    def _get_provider(self) -> LLMProvider:
        if self._provider is None:
            self._provider = self._runtime.get_provider(self.backend)
        return self._provider

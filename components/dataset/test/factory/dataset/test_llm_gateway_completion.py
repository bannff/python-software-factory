"""Tests for the llm_gateway-routed CompletionPort adapter."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from factory.dataset.runtime.adapters.llm_gateway_completion import (
    LLMGatewayCompletionAdapter,
)


@dataclass
class _FakeResponse:
    content: str = "hello from provider"


class _FakeProvider:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls: list[dict] = []

    def chat(self, messages, model=None, **kwargs):
        self.calls.append({"messages": messages, "model": model, **kwargs})
        if self.failures > 0:
            self.failures -= 1
            raise ConnectionError("transient")
        return _FakeResponse()


@dataclass
class _FakeRuntime:
    provider: _FakeProvider = field(default_factory=_FakeProvider)

    @staticmethod
    def available_backends() -> list[str]:
        return ["ollama", "openai", "anthropic", "bedrock"]

    def get_provider(self, backend: str):
        return self.provider


def test_adapter_binds_backend_model_and_routes_chat() -> None:
    runtime = _FakeRuntime()
    adapter = LLMGatewayCompletionAdapter("ollama", model="llama3.2", runtime=runtime)

    result = adapter.get_completion("prompt", system_prompt="system")

    assert result == "hello from provider"
    assert adapter.model_id == "llama3.2"
    call = runtime.provider.calls[0]
    assert call["model"] == "llama3.2"
    assert [(m.role, m.content) for m in call["messages"]] == [
        ("system", "system"),
        ("user", "prompt"),
    ]


def test_adapter_uses_default_model_when_model_is_omitted() -> None:
    adapter = LLMGatewayCompletionAdapter("openai", runtime=_FakeRuntime())
    assert adapter.model_id == "gpt-4o"


def test_adapter_rejects_unsupported_backend() -> None:
    with pytest.raises(ValueError, match="Unsupported LLM backend 'fake'"):
        LLMGatewayCompletionAdapter("fake", runtime=_FakeRuntime())


def test_per_call_values_override_bound_defaults() -> None:
    runtime = _FakeRuntime()
    adapter = LLMGatewayCompletionAdapter(
        "ollama", temperature=0.2, max_tokens=64, runtime=runtime
    )

    adapter.get_completion("p")
    assert runtime.provider.calls[0]["temperature"] == 0.2
    assert runtime.provider.calls[0]["max_tokens"] == 64

    adapter.get_completion("p", temperature=0.9, max_tokens=128)
    assert runtime.provider.calls[1]["temperature"] == 0.9
    assert runtime.provider.calls[1]["max_tokens"] == 128


def test_unbound_sampling_params_are_omitted() -> None:
    runtime = _FakeRuntime()
    adapter = LLMGatewayCompletionAdapter("ollama", runtime=runtime)

    adapter.get_completion("p")

    assert "temperature" not in runtime.provider.calls[0]
    assert "max_tokens" not in runtime.provider.calls[0]


def test_retry_recovers_from_transient_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _FakeRuntime(provider=_FakeProvider(failures=2))
    adapter = LLMGatewayCompletionAdapter("ollama", num_retries=2, runtime=runtime)
    monkeypatch.setattr("factory.dataset.runtime.adapters.llm_gateway_completion.time.sleep", lambda s: None)

    assert adapter.get_completion("p") == "hello from provider"
    assert len(runtime.provider.calls) == 3


def test_retry_exhaustion_raises_explicit_error(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _FakeRuntime(provider=_FakeProvider(failures=10))
    adapter = LLMGatewayCompletionAdapter("ollama", num_retries=1, runtime=runtime)
    monkeypatch.setattr("factory.dataset.runtime.adapters.llm_gateway_completion.time.sleep", lambda s: None)

    with pytest.raises(RuntimeError, match="Completion failed after 2 attempts"):
        adapter.get_completion("p")
    assert len(runtime.provider.calls) == 2


def test_adapter_exposes_sorted_available_backends() -> None:
    adapter = LLMGatewayCompletionAdapter("ollama", runtime=_FakeRuntime())
    assert adapter.available_backends == ["anthropic", "bedrock", "ollama", "openai"]

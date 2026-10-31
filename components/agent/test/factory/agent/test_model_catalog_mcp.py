"""Tests for the deterministic ``agent_list_models`` safe catalog tool.

Covers: mixed Bedrock/OpenRouter/Ollama/openai-compat descriptor projection,
typed taxonomy + strict egress (including the #136 ``scope``/``configured``/
``effective_model_id``/``hidden_count``/``unresolved`` fields), the single fixed
unavailable/malformed error, and absence of any secret / base-url /
credential-env metadata from egress.
"""
from __future__ import annotations

import json

import pytest

from factory.agent.mcp.contracts.model_catalog import (
    ChatModelDTO, ModelCatalogInput, ModelCatalogOutput,
)
from factory.agent.mcp.model_catalog_tools import CATALOG_UNAVAILABLE, register
from factory.llm_gateway.interface import ChatModelCatalog, ChatModelDescriptor
from factory.mcp_utils.interface import ToolCatalog

_MIXED = (
    ChatModelDescriptor(model_id="anthropic.claude", provider="bedrock", model="anthropic.claude"),
    ChatModelDescriptor(model_id="openrouter/deepseek/v4", provider="openrouter", model="deepseek/v4"),
    ChatModelDescriptor(model_id="ollama/llama3", provider="ollama", model="llama3"),
    ChatModelDescriptor(model_id="openai-compat/lm-studio", provider="openai-compat", model="local-model"),
)


def _catalog(
    *models: ChatModelDescriptor, scope: str = "configured", hidden_count: int = 0,
    unresolved: tuple[str, ...] = (),
) -> ChatModelCatalog:
    return ChatModelCatalog(
        models=tuple(models), scope=scope, hidden_count=hidden_count, unresolved=unresolved,
    )


async def _tool():
    catalog = ToolCatalog("test")
    register(catalog, None)
    tools = {tool.name: tool for tool in await catalog.list_tools()}
    return tools["agent_list_models"]


@pytest.mark.asyncio
async def test_tool_is_registered_and_tagged_deterministic() -> None:
    tool = await _tool()
    assert tool.fn._mcp_category == "deterministic"


@pytest.mark.asyncio
async def test_mixed_provider_descriptors_project_to_typed_egress(monkeypatch) -> None:
    monkeypatch.setattr(
        "factory.llm_gateway.interface.list_chat_models",
        lambda **_: _catalog(*_MIXED, hidden_count=449, unresolved=("openrouter/gone",)),
    )
    result = (await _tool()).fn(scope="all", include=["openrouter/gone"])
    assert result.ok is True
    assert isinstance(result.data, ModelCatalogOutput)
    assert result.data.count == 4
    assert result.data.scope == "configured" and result.data.hidden_count == 449
    assert result.data.unresolved == ["openrouter/gone"]
    assert [(m.model_id, m.provider, m.model) for m in result.data.models] == [
        ("anthropic.claude", "bedrock", "anthropic.claude"),
        ("openrouter/deepseek/v4", "openrouter", "deepseek/v4"),
        ("ollama/llama3", "ollama", "llama3"),
        ("openai-compat/lm-studio", "openai-compat", "local-model"),
    ]
    assert [m.effective_model_id for m in result.data.models] == [
        "bedrock/anthropic.claude", "openrouter/deepseek/v4",
        "ollama/llama3", "openai-compat/local-model",
    ]
    assert all(m.configured for m in result.data.models)


def test_egress_dto_exposes_only_safe_fields_and_forbids_extras() -> None:
    assert set(ChatModelDTO.model_fields) == {
        "model_id", "provider", "model", "effective_model_id", "configured",
        "prompt_usd_per_token", "completion_usd_per_token",
    }
    with pytest.raises(Exception):
        ChatModelDTO(model_id="a", provider="b", model="c", base_url="x")


def test_include_selectors_are_bounded_and_rejected_not_dropped() -> None:
    for bad in ([""], ["   "], ["x" * 257], ["openrouter/x", "bad\nselector"],
                [f"selectors/{i}" for i in range(5)]):
        with pytest.raises(Exception):
            ModelCatalogInput(include=bad)
    assert ModelCatalogInput(include=[" openrouter/x "]).include == ["openrouter/x"]
    assert ModelCatalogInput().include == []


@pytest.mark.asyncio
async def test_foreign_rows_stay_marked_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(
        "factory.llm_gateway.interface.list_chat_models",
        lambda **_: _catalog(*(_MIXED[0], ChatModelDescriptor(
            model_id="openrouter/gpt-5", provider="openrouter", model="openai/gpt-5",
            configured=False,
        ))),
    )
    result = (await _tool()).fn()
    assert [m.configured for m in result.data.models] == [True, False]


@pytest.mark.asyncio
async def test_openrouter_pricing_projects_through_non_openrouter_stays_none(monkeypatch) -> None:
    from factory.llm_gateway.interface import ModelPricing

    priced = (
        ChatModelDescriptor(
            model_id="openrouter/deepseek/v4", provider="openrouter", model="deepseek/v4",
            pricing=ModelPricing(prompt_usd_per_token=0.0000002, completion_usd_per_token=0.0000008),
        ),
        ChatModelDescriptor(model_id="anthropic.claude", provider="bedrock", model="anthropic.claude"),
    )
    monkeypatch.setattr(
        "factory.llm_gateway.interface.list_chat_models", lambda **_: _catalog(*priced),
    )
    result = (await _tool()).fn()
    assert result.ok is True
    by_provider = {m.provider: m for m in result.data.models}
    assert by_provider["openrouter"].prompt_usd_per_token == 0.0000002
    assert by_provider["openrouter"].completion_usd_per_token == 0.0000008
    assert by_provider["bedrock"].prompt_usd_per_token is None
    assert by_provider["bedrock"].completion_usd_per_token is None


@pytest.mark.asyncio
async def test_unavailable_catalog_maps_to_fixed_safe_error(monkeypatch) -> None:
    def _raise(**_) -> ChatModelCatalog:
        raise ValueError("chat model catalog unavailable")

    monkeypatch.setattr("factory.llm_gateway.interface.list_chat_models", _raise)
    result = (await _tool()).fn()
    assert result.ok is False
    assert result.data is None
    assert result.error == CATALOG_UNAVAILABLE


@pytest.mark.asyncio
async def test_malformed_catalog_maps_to_same_fixed_error(monkeypatch) -> None:
    def _raise(**_) -> ChatModelCatalog:
        raise ValueError("garbage profile payload http://10.0.0.1 SENTINEL")

    monkeypatch.setattr("factory.llm_gateway.interface.list_chat_models", _raise)
    result = (await _tool()).fn(scope="all")
    assert result.ok is False and result.error == CATALOG_UNAVAILABLE
    assert "SENTINEL" not in json.dumps(result.model_dump())


@pytest.mark.asyncio
async def test_egress_excludes_secret_base_url_and_credential_env(monkeypatch) -> None:
    monkeypatch.setattr(
        "factory.llm_gateway.interface.list_chat_models", lambda **_: _catalog(*_MIXED),
    )
    result = (await _tool()).fn()
    serialized = json.dumps(result.model_dump())
    for leak in ("BASE_URL", "API_KEY", "http://", "https://", "base_url", "api_key"):
        assert leak not in serialized


@pytest.mark.asyncio
async def test_real_env_delegation_lists_bedrock_default_and_compat(monkeypatch) -> None:
    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", "anthropic.claude-v3")
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_PROFILES", "lm-studio")
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("LM_STUDIO_API_KEY", "sentinel-secret")
    monkeypatch.setenv("LM_STUDIO_MODEL", "local-model")
    result = (await _tool()).fn()
    assert result.ok is True
    providers = {m.provider for m in result.data.models}
    assert providers == {"bedrock", "openai-compat"}
    assert "sentinel-secret" not in json.dumps(result.model_dump())
    assert "127.0.0.1" not in json.dumps(result.model_dump())

"""Startup-only composition and strict economy backend regression tests."""
from __future__ import annotations

import asyncio

import pytest

from factory.blockchain.runtime.composition import (
    BlockchainComposition, BlockchainConfigurationError, ProfileDefinition,
    ProfileRegistration,
)
from factory.blockchain.runtime.composition.factory import BlockchainCompositionFactory
from factory.blockchain.runtime.runtime import BlockchainRuntime


def _registration(profile_id: str = "economy", backends: tuple[str, ...] = ("mock",)):
    return ProfileRegistration(ProfileDefinition(profile_id, profile_id), backends)


def test_default_composition_is_immutable_economy_mock(monkeypatch) -> None:
    monkeypatch.delenv("BLOCKCHAIN_ADAPTER", raising=False)
    composition, profile = BlockchainCompositionFactory().create()
    assert composition.backend_id == "mock"
    assert profile.ledger.health_check()["provider"] == "mock_ledger"
    with pytest.raises(TypeError):
        composition.registrations["other"] = _registration("other")  # type: ignore[index]


def test_legacy_mock_alias_and_neo4j_are_explicitly_normalized(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_ADAPTER", "mock_ledger")
    assert BlockchainRuntime().adapter_id == "mock"
    assert BlockchainCompositionFactory("neo4j").backend_id == "neo4j"


def test_unknown_backend_loud_fails_without_mock_fallback(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_ADAPTER", "unknown")
    with pytest.raises(BlockchainConfigurationError, match="BLOCKCHAIN_ADAPTER='unknown'"):
        BlockchainRuntime()


def test_invalid_compositions_fail_before_profile_runtime_creation() -> None:
    duplicate = (_registration(), _registration())
    with pytest.raises(BlockchainConfigurationError, match="Duplicate profile ID"):
        BlockchainComposition.create(duplicate, "mock")
    with pytest.raises(BlockchainConfigurationError, match="Duplicate backend ID"):
        BlockchainComposition.create((_registration(backends=("mock", "mock")),), "mock")
    other_profile = ProfileRegistration(ProfileDefinition("other", "economy"), ("mock",))
    with pytest.raises(BlockchainConfigurationError, match="Only the economy profile"):
        BlockchainComposition.create((other_profile,), "mock")
    with pytest.raises(BlockchainConfigurationError, match="Invalid BLOCKCHAIN_ADAPTER"):
        BlockchainComposition.create((_registration(),), "neo4j")


def test_untrusted_runtime_factory_is_rejected_at_composition_startup() -> None:
    registration = ProfileRegistration(
        ProfileDefinition("economy", "untrusted_factory"), ("mock",),
    )
    with pytest.raises(BlockchainConfigurationError, match="Untrusted runtime factory"):
        BlockchainComposition.create((registration,), "mock")


def test_runtime_builds_composition_once_before_static_tool_registration(monkeypatch) -> None:
    from factory.blockchain.mcp import deterministic
    from factory.blockchain.runtime.composition.factory import BlockchainCompositionFactory
    from factory.blockchain.server import create_mcp_server

    original_create = BlockchainCompositionFactory.create
    original_register = deterministic.register
    calls = 0
    complete = False

    def create_once(factory):
        nonlocal calls, complete
        calls += 1
        result = original_create(factory)
        complete = True
        return result

    def register_after_composition(mcp, get_runtime):
        assert complete
        return original_register(mcp, get_runtime)

    monkeypatch.setattr(BlockchainCompositionFactory, "create", create_once)
    monkeypatch.setattr(deterministic, "register", register_after_composition)
    server = create_mcp_server()
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    assert calls == 1
    tools["blockchain_get_chain_info"].fn()
    assert calls == 1

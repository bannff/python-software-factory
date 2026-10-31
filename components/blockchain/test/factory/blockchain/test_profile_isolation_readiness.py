"""Economy-only startup readiness; external Neo4j conformance is intentionally not invoked."""
from __future__ import annotations

import asyncio

import pytest

from factory.blockchain.runtime.composition import BlockchainCompositionFactory, BlockchainConfigurationError
from factory.blockchain.server import create_mcp_server


def test_only_economy_is_mounted_and_no_dcal_surface_is_discoverable() -> None:
    composition, _runtime = BlockchainCompositionFactory("mock").create()
    assert composition.active_profile_id == "economy"
    assert tuple(composition.registrations) == ("economy",)
    server = create_mcp_server(_runtime)
    tools = asyncio.run(server.list_tools())
    resources = asyncio.run(server.list_resources())
    templates = asyncio.run(server.list_resource_templates())
    prompts = asyncio.run(server.list_prompts())
    names = ([tool.name for tool in tools] + [str(item.uri) for item in resources]
             + [item.uri_template for item in templates] + [item.name for item in prompts])
    assert not any("dcal" in name.lower() for name in names)


def test_unmounted_profile_and_invalid_backend_cannot_fall_back_to_economy_state() -> None:
    with pytest.raises(BlockchainConfigurationError, match="Only the economy profile"):
        BlockchainCompositionFactory("mock", registrations=()).create()
    with pytest.raises(BlockchainConfigurationError, match="Invalid BLOCKCHAIN_ADAPTER"):
        BlockchainCompositionFactory("unavailable").create()


def test_neo4j_is_configured_but_external_conformance_is_not_a_local_requirement() -> None:
    factory = BlockchainCompositionFactory("neo4j")
    assert factory.backend_id == "neo4j"
    pytest.skip("Neo4j adapter conformance requires externally provisioned graph infrastructure")

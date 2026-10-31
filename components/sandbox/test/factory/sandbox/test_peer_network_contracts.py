"""Peer-network contracts: model validation, profile metadata, MCP boundary."""

from __future__ import annotations

import pytest
from factory.sandbox.mcp.models import SandboxProvisionRequest
from factory.sandbox.runtime.models import SandboxConfig
from factory.sandbox.runtime.peer_network import PeerNetworkSpec
from factory.sandbox.runtime.profiles import SandboxProfile
from factory.sandbox.runtime.provision_context import build_provision_context
from pydantic import ValidationError


@pytest.mark.parametrize("data", [
    {"network_id": "../host", "alias": "peer-a", "port": 1234},
    {"network_id": "Mesh", "alias": "peer-a", "port": 1234},
    {"network_id": "mesh", "alias": "Peer-A", "port": 1234},
    {"network_id": "mesh", "alias": "peer-a;id", "port": 1234},
    {"network_id": "mesh", "alias": "peer-a", "port": 65536},
    {"network_id": "mesh", "alias": "peer-a", "port": 0},
    {"network_id": "mesh", "alias": "peer-a", "port": "1234"},
    {"network_id": "mesh", "alias": "peer-a", "port": True},
    {"network_id": "mesh", "alias": "peer-a", "port": 1234, "internal": "true"},
    {"network_id": "mesh", "alias": "peer-a", "port": 1234, "extra": True},
])
def test_peer_network_rejects_invalid_boundary_values(data: dict) -> None:
    with pytest.raises(ValidationError):
        PeerNetworkSpec.model_validate(data)


def test_profile_accepts_mesh_and_legacy_profile_unchanged() -> None:
    legacy = SandboxProfile(name="plain", image="alpine:3.20")
    mesh = SandboxProfile(
        name="mesh", image="alpine:3.20",
        peer_network={"network_id": "factory-test", "alias": "peer-a", "port": 4321},
    )
    assert legacy.peer_network is None
    assert mesh.peer_network.endpoint == "peer-a:4321"


def test_profile_provision_context_exposes_endpoint_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    (tmp_path / "mesh.yaml").write_text(
        "image: alpine:3.20\n"
        "peer_network:\n"
        "  network_id: factory-test\n"
        "  alias: peer-a\n"
        "  port: 4321\n"
        "  internal: true\n"
    )
    config, metadata, _ = build_provision_context(SandboxConfig(), "mesh")
    assert config["peer_network"] == {
        "network_id": "factory-test", "alias": "peer-a", "port": 4321,
        "internal": True,
    }
    assert metadata["peer_network"]["endpoint"] == "peer-a:4321"
    assert metadata["peer_network"]["internal"] is True


def test_internal_profile_network_rejects_host_port_mapping(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    (tmp_path / "mesh.yaml").write_text(
        "image: alpine:3.20\n"
        "ports: {'8080': '80'}\n"
        "peer_network:\n"
        "  network_id: factory-test\n"
        "  alias: peer-a\n"
        "  port: 4321\n"
        "  internal: true\n"
    )
    with pytest.raises(ValueError, match="cannot publish profile ports"):
        build_provision_context(SandboxConfig(), "mesh")


def test_mcp_provision_boundary_accepts_peer_and_requires_profile() -> None:
    request = SandboxProvisionRequest.model_validate({
        "profile": "edge-lab",
        "peer_network": {"network_id": "mesh-a", "alias": "edge-peer-b", "port": 24225},
    })
    assert request.peer_network.endpoint == "edge-peer-b:24225"
    with pytest.raises(ValidationError):
        SandboxProvisionRequest.model_validate({
            "peer_network": {"network_id": "mesh-a", "alias": "edge-peer-b", "port": 24225},
        })

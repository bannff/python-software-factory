"""Security contract tests for Agent-only steer acknowledgement binding."""
from __future__ import annotations

import pytest

from factory.mcp_utils.interface import SteerBinding, service_only
from factory.mcp_utils.service_bindings import binding_kind, binding_matches


def _binding(**overrides) -> SteerBinding:
    values = {
        "tenant_id": "tenant:local",
        "owner_id": "svc:local",
        "session_id": "session_1",
        "delivery_id": "delivery_1",
        "revision": 2,
    }
    values.update(overrides)
    return SteerBinding(**values)


def test_steer_binding_kind_and_validation() -> None:
    assert binding_kind(_binding()) == "steer"
    with pytest.raises(ValueError, match="tenant_id"):
        _binding(tenant_id="")
    with pytest.raises(ValueError, match="revision"):
        _binding(revision=0)
    with pytest.raises(ValueError, match="revision"):
        _binding(revision=True)


def test_steer_binding_matches_every_exact_argument() -> None:
    binding = _binding()
    good = {
        "tenant_id": "tenant:local",
        "owner_id": "svc:local",
        "session_id": "session_1",
        "delivery_id": "delivery_1",
        "revision": 2,
    }
    assert binding_matches(binding, good)
    for field in good:
        assert not binding_matches(binding, {**good, field: "other"})
    assert not binding_matches(binding, {key: value for key, value in good.items() if key != "owner_id"})


def test_service_only_accepts_agent_steer_binding() -> None:
    @service_only(callers={"agent"}, binding="steer")
    def acknowledge() -> None:
        return None

    assert acknowledge._mcp_service_binding == "steer"
    assert acknowledge._mcp_service_callers == frozenset({"agent"})

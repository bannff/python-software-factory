"""Tests for immutable one-surface composition planning."""

import pytest

from factory.mcp_utils.interface import ServerCompositionPlan, ServerSurfaceIdentity


def _identity(**changes: str) -> ServerSurfaceIdentity:
    values = {
        "entry_point": "factory.mcp_server:main",
        "route_bindings": ("/mcp",),
        "transport_bindings": ("http", "stdio", "in_process"),
        "process_lifecycle_id": "factory-process",
        "catalog_digest": "catalog",
        "scope_digest": "scope",
        "policy_digest": "policy",
        "closure_digest": "closure",
    }
    values.update(changes)
    return ServerSurfaceIdentity(**values)


def test_equivalent_identity_is_order_independent_and_bound_to_one_plan() -> None:
    first = _identity()
    second = ServerSurfaceIdentity(
        "factory.mcp_server:main", ("/mcp",), ("in_process", "http", "stdio"),
        "factory-process", "catalog", "scope", "policy", "closure",
    )
    plan = ServerCompositionPlan(first, "progressive", frozenset({"memory_get"}))
    assert first.digest == second.digest
    assert plan.identity == first


@pytest.mark.parametrize("field", ["scope_digest", "catalog_digest", "policy_digest", "closure_digest"])
def test_identity_digest_changes_when_a_bound_fact_changes(field: str) -> None:
    original = _identity()
    assert _identity(**{field: "changed"}).digest != original.digest


def test_identity_rejects_duplicate_bindings() -> None:
    with pytest.raises(ValueError, match="unique"):
        ServerSurfaceIdentity(
            "entry", ("/mcp", "/mcp"), ("http",), "lifecycle",
            "catalog", "scope", "policy", "closure",
        )

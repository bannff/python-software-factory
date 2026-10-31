"""Trusted runtime adapter registry tests."""

import pytest

from factory.agent.runtime.adapter_registry import (
    RuntimeAdapterFactory,
    get_runtime_adapter,
    register_runtime_adapter,
)


def _factory(adapter_id: str) -> RuntimeAdapterFactory:
    return RuntimeAdapterFactory(
        adapter_id, lambda: "agent", lambda: "chat",
        lambda: "graph", lambda: "coordination",
    )


def test_registry_resolves_one_trusted_adapter() -> None:
    adapter = _factory("test-runtime-registry")
    register_runtime_adapter(adapter)
    assert get_runtime_adapter(adapter.adapter_id) is adapter


def test_registry_rejects_duplicates_and_unknown_ids() -> None:
    adapter = _factory("test-runtime-duplicate")
    register_runtime_adapter(adapter)
    with pytest.raises(ValueError, match="duplicate"):
        register_runtime_adapter(adapter)
    with pytest.raises(ValueError, match="unknown"):
        get_runtime_adapter("missing-runtime")

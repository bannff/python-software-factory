"""Tests for the in-memory policy store adapter."""

from __future__ import annotations

import pytest

from factory.permissions.runtime.models import PolicyDefinition, Rule
from factory.permissions.runtime.storage import MemoryPolicyStore, create_store


def _make_policy(policy_id: str, name: str | None = None) -> PolicyDefinition:
    """Create a simple test policy."""
    return PolicyDefinition(
        id=policy_id,
        name=name or f"Test Policy {policy_id}",
        rules=[
            Rule(
                id="rule-1",
                effect="allow",
                actions=["read"],
                resource_types=["document"],
            )
        ],
    )


class TestMemoryPolicyStore:
    """Tests for MemoryPolicyStore."""

    def test_empty_store_returns_empty_list(self) -> None:
        store = MemoryPolicyStore()
        assert store.load_policies() == []

    def test_add_and_load_policy(self) -> None:
        store = MemoryPolicyStore()
        policy = _make_policy("policy-1")

        store.add_policy(policy)
        policies = store.load_policies()

        assert len(policies) == 1
        assert policies[0].id == "policy-1"

    def test_add_multiple_policies(self) -> None:
        store = MemoryPolicyStore()
        store.add_policy(_make_policy("policy-1"))
        store.add_policy(_make_policy("policy-2"))
        store.add_policy(_make_policy("policy-3"))

        policies = store.load_policies()
        assert len(policies) == 3
        policy_ids = {p.id for p in policies}
        assert policy_ids == {"policy-1", "policy-2", "policy-3"}

    def test_update_existing_policy(self) -> None:
        store = MemoryPolicyStore()
        store.add_policy(_make_policy("policy-1", name="Original"))
        store.add_policy(_make_policy("policy-1", name="Updated"))

        policies = store.load_policies()
        assert len(policies) == 1
        assert policies[0].name == "Updated"

    def test_remove_policy(self) -> None:
        store = MemoryPolicyStore()
        store.add_policy(_make_policy("policy-1"))
        store.add_policy(_make_policy("policy-2"))

        removed = store.remove_policy("policy-1")
        assert removed is True
        assert store.policy_count() == 1

    def test_remove_nonexistent_policy(self) -> None:
        store = MemoryPolicyStore()
        removed = store.remove_policy("nonexistent")
        assert removed is False

    def test_get_policy(self) -> None:
        store = MemoryPolicyStore()
        policy = _make_policy("policy-1")
        store.add_policy(policy)

        retrieved = store.get_policy("policy-1")
        assert retrieved is not None
        assert retrieved.id == "policy-1"

    def test_get_nonexistent_policy(self) -> None:
        store = MemoryPolicyStore()
        retrieved = store.get_policy("nonexistent")
        assert retrieved is None

    def test_clear(self) -> None:
        store = MemoryPolicyStore()
        store.add_policy(_make_policy("policy-1"))
        store.add_policy(_make_policy("policy-2"))

        count = store.clear()
        assert count == 2
        assert store.policy_count() == 0
        assert store.load_policies() == []

    def test_policy_count(self) -> None:
        store = MemoryPolicyStore()
        assert store.policy_count() == 0

        store.add_policy(_make_policy("policy-1"))
        assert store.policy_count() == 1

        store.add_policy(_make_policy("policy-2"))
        assert store.policy_count() == 2

    def test_health_check(self) -> None:
        store = MemoryPolicyStore()
        store.add_policy(_make_policy("policy-1"))

        health = store.health_check()
        assert health["ok"] is True
        assert health["backend"] == "memory"
        assert health["policy_count"] == 1
        assert health["last_error"] is None


class TestCreateStoreFactory:
    """Tests for the create_store factory function."""

    def test_create_memory_store_default(self) -> None:
        store = create_store()
        assert isinstance(store, MemoryPolicyStore)

    def test_create_memory_store_explicit(self) -> None:
        store = create_store(store_type="memory")
        assert isinstance(store, MemoryPolicyStore)

    def test_create_filesystem_store(self, tmp_path) -> None:
        store = create_store(store_type="filesystem", config_dir=tmp_path)
        # Import here to check type
        from factory.permissions.runtime.storage.filesystem import FilesystemPolicyStore

        assert isinstance(store, FilesystemPolicyStore)

    def test_filesystem_store_requires_config_dir(self) -> None:
        with pytest.raises(ValueError, match="config_dir is required"):
            create_store(store_type="filesystem")

    def test_unknown_store_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown store type"):
            create_store(store_type="unknown")

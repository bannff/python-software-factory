"""In-memory policy store adapter.

Provides a simple in-memory implementation of the PolicyStore protocol
for testing and development scenarios where filesystem access is not needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from factory.permissions.runtime.models import PolicyDefinition
from factory.permissions.runtime.ports import PolicyStore


@dataclass
class MemoryPolicyStore(PolicyStore):
    """In-memory implementation of PolicyStore protocol.

    Stores policies in a dictionary keyed by policy ID.
    Ideal for testing and development scenarios.
    """

    _policies: dict[str, PolicyDefinition] = field(default_factory=dict)
    _last_error: str | None = None

    def load_policies(self) -> list[PolicyDefinition]:
        """Return all stored policies as a list."""
        self._last_error = None
        return list(self._policies.values())

    def health_check(self) -> dict[str, object]:
        """Return health status of the memory store."""
        return {
            "ok": True,
            "backend": "memory",
            "policy_count": len(self._policies),
            "last_error": self._last_error,
        }

    def add_policy(self, policy: PolicyDefinition) -> None:
        """Add or update a policy in the store."""
        self._policies[policy.id] = policy

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy by ID. Returns True if removed, False if not found."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def get_policy(self, policy_id: str) -> PolicyDefinition | None:
        """Get a policy by ID. Returns None if not found."""
        return self._policies.get(policy_id)

    def clear(self) -> int:
        """Clear all policies. Returns the count of removed policies."""
        count = len(self._policies)
        self._policies.clear()
        return count

    def policy_count(self) -> int:
        """Return the number of stored policies."""
        return len(self._policies)

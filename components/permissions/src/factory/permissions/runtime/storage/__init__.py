"""Policy storage adapters.

Provides factory function to create appropriate PolicyStore implementation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from factory.permissions.runtime.ports import PolicyStore
from factory.permissions.runtime.storage.memory import MemoryPolicyStore

if TYPE_CHECKING:
    from factory.permissions.runtime.storage.filesystem import FilesystemPolicyStore

__all__ = ["MemoryPolicyStore", "FilesystemPolicyStore", "create_store"]


def create_store(
    store_type: str = "memory",
    config_dir: str | Path | None = None,
    policies_subdir: str = "policies",
) -> PolicyStore:
    """Create a PolicyStore instance based on the specified type.

    Args:
        store_type: Type of store to create ("memory" or "filesystem").
        config_dir: Configuration directory (required for filesystem store).
        policies_subdir: Subdirectory for policies (filesystem store only).

    Returns:
        A PolicyStore implementation.

    Raises:
        ValueError: If store_type is "filesystem" but config_dir is not provided.
        ValueError: If store_type is unknown.
    """
    if store_type == "memory":
        return MemoryPolicyStore()

    if store_type == "filesystem":
        if config_dir is None:
            raise ValueError("config_dir is required for filesystem store")
        # Lazy import to avoid filesystem dependencies when not needed
        from factory.permissions.runtime.storage.filesystem import FilesystemPolicyStore

        return FilesystemPolicyStore(
            config_dir=Path(config_dir),
            policies_subdir=policies_subdir,
        )

    raise ValueError(f"Unknown store type: {store_type}")

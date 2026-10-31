"""Artifacts runtime composition."""
from __future__ import annotations

import os
from typing import Any

from factory.storage.interface import get_sql_store

from .adapters import SQLArtifactStore
from .adapters.local_publish_provider import LocalPublishProvider
from .comments import CommentLifecycle
from .lifecycle import ArtifactLifecycle
from .organization import OrganizationLifecycle
from .publish import PublishProviderRegistry
from .publish_lifecycle import PublishLifecycle


class ArtifactsRuntime:
    def __init__(self, lifecycle: ArtifactLifecycle | None = None) -> None:
        self._lifecycle = lifecycle
        self._organization: OrganizationLifecycle | None = None
        self._comments: CommentLifecycle | None = None
        self._publish: PublishLifecycle | None = None

    @property
    def publish(self) -> PublishLifecycle:
        if self._publish is None:
            self._publish = PublishLifecycle(
                self.lifecycle.store,
                PublishProviderRegistry({"local": LocalPublishProvider()}),
            )
        return self._publish

    @property
    def organization(self) -> OrganizationLifecycle:
        if self._organization is None:
            self._organization = OrganizationLifecycle(self.lifecycle.store)
        return self._organization

    @property
    def comments(self) -> CommentLifecycle:
        if self._comments is None:
            self._comments = CommentLifecycle(self.lifecycle.store)
        return self._comments

    @property
    def lifecycle(self) -> ArtifactLifecycle:
        if self._lifecycle is None:
            backend = os.getenv("FACTORY_ARTIFACTS_ADAPTER", "sqlite")
            if backend != "sqlite":
                raise ValueError("artifacts adapter unsupported")
            path = os.getenv("COMPANION_X_ARTIFACTS_DB_PATH", "./.storage/artifacts.db")
            self._lifecycle = ArtifactLifecycle(
                SQLArtifactStore(get_sql_store("sqlite", db_path=path)),
            )
        return self._lifecycle

    @staticmethod
    def get_capabilities() -> dict[str, Any]:
        return {"name": "artifacts", "version": "1.0.0", "features": [
            "stable_owner_scoped_slugs", "idempotent_save",
            "immutable_version_snapshots", "revision_fenced_lifecycle",
            "additive_version_revert", "opaque_tombstones",
            "content_free_lifecycle_events", "bounded_owner_scoped_folders",
            "one_level_comment_threads", "human_gated_authoring",
            "native_mcp_v2_typed_pydantic_contracts",
        ]}

    @staticmethod
    def health_check() -> dict[str, Any]:
        return {"healthy": True, "backend": "sqlite"}


_runtime: ArtifactsRuntime | None = None


def get_runtime() -> ArtifactsRuntime:
    global _runtime
    if _runtime is None:
        _runtime = ArtifactsRuntime()
    return _runtime


__all__ = ["ArtifactsRuntime", "get_runtime"]

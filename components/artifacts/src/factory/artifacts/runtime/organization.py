"""Artifact folder lifecycle and membership policy."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .models import ArtifactFolder, ArtifactRecord, validate_folder_name
from .ports import ArtifactConflictError, ArtifactStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrganizationLifecycle:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def create(self, tenant: str, owner: str, name: str,
               parent_id: str | None = None) -> ArtifactFolder:
        folder_id = uuid4().hex
        now = datetime.now(timezone.utc)
        clean_name = validate_folder_name(name)
        result = self.store.create_folder(
            tenant, owner, folder_id, clean_name, parent_id, now.isoformat(),
        )
        if result is None:
            raise ValueError("folder_not_found_or_conflict")
        return result

    def list(self, tenant: str, owner: str) -> list[ArtifactFolder]:
        return self.store.list_folders(tenant, owner)

    def rename(self, tenant: str, owner: str, folder_id: str,
               expected: int, name: str) -> ArtifactFolder:
        now = datetime.now(timezone.utc)
        clean_name = validate_folder_name(name)
        result = self.store.rename_folder(
            tenant, owner, folder_id, expected, clean_name, now.isoformat(),
        )
        if result is None:
            raise ArtifactConflictError("folder revision conflict")
        return result

    def move(self, tenant: str, owner: str, folder_id: str, expected: int,
             parent_id: str | None) -> ArtifactFolder:
        result = self.store.move_folder(
            tenant, owner, folder_id, expected, parent_id, _now(),
        )
        if result is None:
            raise ArtifactConflictError("folder move conflict")
        return result

    def delete(self, tenant: str, owner: str, folder_id: str,
               expected: int) -> None:
        if not self.store.delete_folder(
            tenant, owner, folder_id, expected, _now(),
        ):
            raise ArtifactConflictError("folder revision conflict")

    def move_artifact(self, tenant: str, owner: str, slug: str, expected: int,
                      folder_id: str | None) -> ArtifactRecord:
        result = self.store.move_artifact(
            tenant, owner, slug, expected, folder_id, _now(),
        )
        if result is None:
            raise ArtifactConflictError("artifact revision conflict")
        return result


__all__ = ["OrganizationLifecycle"]

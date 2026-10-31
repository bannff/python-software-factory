"""Artifacts persistence port."""
from __future__ import annotations

from typing import Protocol

from .models import (
    ActorKind, ArtifactComment, ArtifactFolder, ArtifactKind,
    ArtifactMutationEventType, ArtifactRecord, ArtifactVersion,
    ArtifactWriteResult, PublicationNotice,
)


class ArtifactConflictError(RuntimeError):
    """Owner-scoped artifact idempotency or revision conflict."""


class ArtifactSlugExhaustedError(RuntimeError):
    """Bounded same-owner slug namespace is exhausted."""


class ArtifactStore(Protocol):
    def save(self, tenant_id: str, owner_id: str, name: str, content: str, *,
             description: str, kind: ArtifactKind, tags: tuple[str, ...],
             actor_kind: ActorKind, idempotency_key: str | None,
             request_sha256: str, content_sha256: str) -> ArtifactWriteResult: ...
    def get(self, tenant_id: str, owner_id: str,
            slug: str) -> ArtifactRecord | None: ...
    def list(self, tenant_id: str, owner_id: str, *, limit: int, offset: int,
             name: str | None, kind: ArtifactKind | None,
             tag: str | None) -> list[ArtifactRecord]: ...
    def get_version(self, tenant_id: str, owner_id: str, slug: str,
                    version: int) -> ArtifactVersion | None: ...
    def update(self, tenant_id: str, owner_id: str, slug: str,
               expected_revision: int, *, actor_kind: ActorKind,
               event_type: ArtifactMutationEventType,
               name: str | None = None, description: str | None = None,
               kind: ArtifactKind | None = None,
               tags: tuple[str, ...] | None = None, content: str | None = None,
               content_sha256: str | None = None) -> ArtifactRecord | None: ...
    def list_versions(self, tenant_id: str, owner_id: str,
                      slug: str) -> list[ArtifactVersion]: ...
    def get_tombstone(self, tenant_id: str, owner_id: str,
                      slug: str) -> ArtifactRecord | None: ...
    def tombstone(self, tenant_id: str, owner_id: str, slug: str,
                  expected_revision: int) -> bool: ...
    def create_folder(self, tenant: str, owner: str, folder_id: str, name: str,
                      parent_id: str | None, now: str) -> ArtifactFolder | None: ...
    def list_folders(self, tenant: str, owner: str) -> list[ArtifactFolder]: ...
    def get_folder(self, tenant: str, owner: str,
                   folder_id: str) -> ArtifactFolder | None: ...
    def rename_folder(self, tenant: str, owner: str, folder_id: str,
                      expected: int, name: str,
                      now: str) -> ArtifactFolder | None: ...
    def move_folder(self, tenant: str, owner: str, folder_id: str,
                    expected: int, parent_id: str | None,
                    now: str) -> ArtifactFolder | None: ...
    def delete_folder(self, tenant: str, owner: str, folder_id: str,
                      expected: int, now: str) -> bool: ...
    def move_artifact(self, tenant: str, owner: str, slug: str, expected: int,
                      folder_id: str | None, now: str) -> ArtifactRecord | None: ...
    def add_comment(self, tenant: str, owner: str, comment_id: str, slug: str,
                    parent_id: str | None, body: str, actor: ActorKind,
                    now: str, anchor_text: str | None = None) -> ArtifactComment | None: ...
    def list_comments(self, tenant: str, owner: str,
                      slug: str) -> list[ArtifactComment]: ...
    def mark_comment_review(self, tenant: str, owner: str, slug: str,
                            comment_id: str, now: str) -> ArtifactComment | None: ...
    def resolve_comment(self, tenant: str, owner: str, slug: str,
                        comment_id: str, expected: int,
                        now: str) -> ArtifactComment | None: ...
    def delete_comment(self, tenant: str, owner: str, slug: str,
                       comment_id: str, expected: int, now: str) -> bool: ...
    def purge_artifact(self, tenant: str, owner: str, slug: str,
                       expected: int, token: str) -> bool: ...
    def upsert_publication(self, tenant: str, owner: str, slug: str,
                           provider: str, external_ref: str, detail: str,
                           now: str) -> "PublicationNotice | None": ...
    def get_publication(self, tenant: str, owner: str, slug: str,
                        provider: str) -> "PublicationNotice | None": ...
    def update_publication_status(self, tenant: str, owner: str, slug: str,
                                  provider: str, status: str, detail: str,
                                  now: str) -> "PublicationNotice | None": ...
    def remove_publication(self, tenant: str, owner: str, slug: str,
                           provider: str) -> bool: ...


__all__ = ["ArtifactConflictError", "ArtifactSlugExhaustedError", "ArtifactStore"]

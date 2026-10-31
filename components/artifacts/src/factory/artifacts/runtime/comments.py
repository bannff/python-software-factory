"""Artifact comment lifecycle and actor policy."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .models import ActorKind, ArtifactComment
from .ports import ArtifactConflictError, ArtifactStore


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CommentLifecycle:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def post(self, tenant: str, owner: str, slug: str, body: str,
             actor: ActorKind, parent_id: str | None = None,
             anchor_text: str | None = None) -> ArtifactComment:
        comment_id = uuid4().hex
        now = _now()
        ArtifactComment(
            tenant_id=tenant, owner_id=owner, id=comment_id, slug=slug,
            root_id=parent_id or comment_id, parent_id=parent_id, body=body,
            actor_kind=actor, status="open", revision=1,
            created_at=now, updated_at=now, anchor_text=anchor_text,
        )
        result = self.store.add_comment(
            tenant, owner, comment_id, slug, parent_id, body,
            actor, now.isoformat(), anchor_text,
        )
        if result is None:
            raise ValueError("artifact_or_comment_not_found_or_limit")
        return result

    def list(self, tenant: str, owner: str, slug: str) -> list[ArtifactComment]:
        if self.store.get(tenant, owner, slug) is None:
            raise ValueError("artifact_not_found")
        return self.store.list_comments(tenant, owner, slug)

    def mark_review(self, tenant: str, owner: str, slug: str,
                    comment_id: str) -> ArtifactComment:
        result = self.store.mark_comment_review(
            tenant, owner, slug, comment_id, _now().isoformat(),
        )
        if result is None:
            raise ValueError("comment_not_found")
        return result

    def resolve(self, tenant: str, owner: str, slug: str, comment_id: str,
                expected: int, actor: ActorKind) -> ArtifactComment:
        self._human(actor)
        result = self.store.resolve_comment(
            tenant, owner, slug, comment_id, expected, _now().isoformat(),
        )
        if result is None:
            raise ArtifactConflictError("comment revision conflict")
        return result

    def delete(self, tenant: str, owner: str, slug: str, comment_id: str,
               expected: int, actor: ActorKind) -> None:
        self._human(actor)
        if not self.store.delete_comment(
            tenant, owner, slug, comment_id, expected, _now().isoformat(),
        ):
            raise ArtifactConflictError("comment revision conflict")

    @staticmethod
    def _human(actor: ActorKind) -> None:
        if actor != "human":
            raise PermissionError("artifact human actor required")


__all__ = ["CommentLifecycle"]

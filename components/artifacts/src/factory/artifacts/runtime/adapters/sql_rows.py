"""Artifacts SQLite schema and row conversion."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..models import (
    ArtifactComment, ArtifactFolder, ArtifactKind, ArtifactRecord, ArtifactVersion,
)

ARTIFACT_SCHEMA = """CREATE TABLE IF NOT EXISTS companion_artifacts (
 tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, slug TEXT NOT NULL,
 name TEXT NOT NULL, description TEXT NOT NULL, kind TEXT NOT NULL,
 tags TEXT NOT NULL, folder_id TEXT, content TEXT NOT NULL, content_sha256 TEXT NOT NULL,
 idempotency_key TEXT, request_sha256 TEXT, version INTEGER NOT NULL,
 revision INTEGER NOT NULL, actor_kind TEXT NOT NULL, event_type TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
 purge_token TEXT,
 PRIMARY KEY (tenant_id, owner_id, slug))"""
IDEMPOTENCY_INDEX = """CREATE UNIQUE INDEX IF NOT EXISTS artifacts_idempotency
 ON companion_artifacts(tenant_id, owner_id, idempotency_key)
 WHERE idempotency_key IS NOT NULL"""
VERSION_SCHEMA = """CREATE TABLE IF NOT EXISTS artifact_versions (
 tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, slug TEXT NOT NULL,
 version INTEGER NOT NULL, content TEXT NOT NULL, content_sha256 TEXT NOT NULL,
 kind TEXT NOT NULL, actor_kind TEXT NOT NULL, event_type TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY (tenant_id, owner_id, slug, version))"""
V1_TRIGGER = """CREATE TRIGGER IF NOT EXISTS artifact_version_one
 AFTER INSERT ON companion_artifacts BEGIN
 INSERT INTO artifact_versions VALUES (
  NEW.tenant_id,NEW.owner_id,NEW.slug,1,NEW.content,NEW.content_sha256,
  NEW.kind,NEW.actor_kind,'created',NEW.created_at);
 END"""
IMMUTABLE_TRIGGER = """CREATE TRIGGER IF NOT EXISTS artifact_version_no_update
 BEFORE UPDATE ON artifact_versions BEGIN
 SELECT RAISE(ABORT, 'artifact version immutable'); END"""
DELETE_GUARD_TRIGGER = """CREATE TRIGGER IF NOT EXISTS artifact_version_no_delete
 BEFORE DELETE ON artifact_versions WHEN COALESCE((SELECT purge_token FROM
  companion_artifacts WHERE tenant_id=OLD.tenant_id AND owner_id=OLD.owner_id
  AND slug=OLD.slug),'')='' AND OLD.version > COALESCE((
  SELECT version - 50 FROM companion_artifacts WHERE tenant_id=OLD.tenant_id
  AND owner_id=OLD.owner_id AND slug=OLD.slug), -1) BEGIN
 SELECT RAISE(ABORT, 'artifact version retained'); END"""
VERSION_UPDATE_TRIGGER = """CREATE TRIGGER IF NOT EXISTS artifact_version_update
 AFTER UPDATE ON companion_artifacts WHEN NEW.version > OLD.version BEGIN
 INSERT INTO artifact_versions VALUES (
  NEW.tenant_id,NEW.owner_id,NEW.slug,NEW.version,NEW.content,
  NEW.content_sha256,NEW.kind,NEW.actor_kind,NEW.event_type,NEW.updated_at);
 DELETE FROM artifact_versions WHERE tenant_id=NEW.tenant_id
  AND owner_id=NEW.owner_id AND slug=NEW.slug
  AND version <= NEW.version - 50;
 END"""


def artifact_from(row: dict[str, Any] | None) -> ArtifactRecord | None:
    if row is None:
        return None
    return ArtifactRecord.model_validate({
        "tenant_id": row["tenant_id"], "owner_id": row["owner_id"],
        "slug": row["slug"], "name": row["name"],
        "description": row["description"], "kind": ArtifactKind(row["kind"]),
        "tags": tuple(json.loads(row["tags"])), "folder_id": row.get("folder_id"),
        "content": row["content"],
        "content_sha256": row["content_sha256"], "version": row["version"],
        "revision": row["revision"],
        "created_at": datetime.fromisoformat(row["created_at"]),
        "updated_at": datetime.fromisoformat(row["updated_at"]),
    })


def version_from(row: dict[str, Any] | None) -> ArtifactVersion | None:
    if row is None:
        return None
    value = dict(row)
    value["kind"] = ArtifactKind(value["kind"])
    value["created_at"] = datetime.fromisoformat(value["created_at"])
    return ArtifactVersion.model_validate(value)


def folder_from(row: dict[str, Any], tenant: str, owner: str) -> ArtifactFolder:
    value = dict(row)
    value["tenant_id"] = tenant
    value["owner_id"] = owner
    value["created_at"] = datetime.fromisoformat(value["created_at"])
    value["updated_at"] = datetime.fromisoformat(value["updated_at"])
    return ArtifactFolder.model_validate(value)


def comment_from(row: dict[str, Any]) -> ArtifactComment:
    value = {key: row[key] for key in (
        "tenant_id", "owner_id", "id", "slug", "root_id", "parent_id",
        "body", "actor_kind", "status", "revision", "created_at", "updated_at",
    )}
    value["anchor_text"] = row.get("anchor_text")
    value["created_at"] = datetime.fromisoformat(value["created_at"])
    value["updated_at"] = datetime.fromisoformat(value["updated_at"])
    return ArtifactComment.model_validate(value)


__all__ = ["ARTIFACT_SCHEMA", "DELETE_GUARD_TRIGGER", "IDEMPOTENCY_INDEX",
           "IMMUTABLE_TRIGGER", "VERSION_SCHEMA", "VERSION_UPDATE_TRIGGER",
           "V1_TRIGGER", "artifact_from", "comment_from", "folder_from",
           "version_from"]

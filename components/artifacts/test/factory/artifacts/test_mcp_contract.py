from __future__ import annotations

import pytest
from pydantic import ValidationError

from factory.artifacts.mcp.contracts import CommentBodyInput, SaveArtifactInput
from factory.artifacts.mcp import support
from factory.artifacts.runtime.adapters.sql import SQLArtifactStore
from factory.artifacts.runtime.lifecycle import ArtifactLifecycle
from factory.artifacts.runtime.runtime import ArtifactsRuntime
from factory.artifacts.server import create_tool_catalog
from factory.storage.runtime.adapters.sql_sqlite import SQLiteSQLStore


def runtime(tmp_path) -> ArtifactsRuntime:
    return ArtifactsRuntime(ArtifactLifecycle(
        SQLArtifactStore(SQLiteSQLStore(str(tmp_path / "artifacts.db"))),
    ))


def test_contract_is_strict_and_byte_bounded() -> None:
    with pytest.raises(ValidationError):
        SaveArtifactInput(name="x", content="x", owner_id="forged")
    with pytest.raises(ValidationError):
        SaveArtifactInput(name="x", content="\ud800")
    with pytest.raises(ValidationError):
        SaveArtifactInput(name="x", content="x" * (1_048_576 + 1))
    with pytest.raises(ValidationError):
        CommentBodyInput(slug="x", body="comment", actor_kind="human")


@pytest.mark.asyncio
async def test_catalog_taxonomy_and_typed_results(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(support, "get_envelope", lambda: {
        "tenant_id": "tenant", "principal_id": "owner", "agent_id": "agent",
    })
    catalog = create_tool_catalog(runtime(tmp_path))
    tools = {tool.name: tool for tool in await catalog.list_tools()}
    assert set(tools) == {
        "artifacts_get", "artifacts_list", "artifacts_versions",
        "artifacts_folder_list", "artifacts_get_comments",
        "artifacts_save", "artifacts_update", "artifacts_revert",
        "artifacts_tombstone", "artifacts_folder_create",
        "artifacts_folder_rename", "artifacts_folder_move",
        "artifacts_folder_delete", "artifacts_move",
        "artifacts_post_comment", "artifacts_reply_comment",
        "artifacts_mark_comment_review", "artifacts_resolve_comment",
        "artifacts_delete_comment", "artifacts_purge",
        "artifacts_publish_providers", "artifacts_publish",
        "artifacts_publish_refresh", "artifacts_get_publication",
        "artifacts_unpublish",
    }
    deterministic_names = (
        "artifacts_get", "artifacts_list", "artifacts_versions",
        "artifacts_folder_list", "artifacts_get_comments",
    )
    operational_names = (
        "artifacts_save", "artifacts_update", "artifacts_revert",
        "artifacts_tombstone", "artifacts_folder_create",
        "artifacts_folder_rename", "artifacts_folder_move",
        "artifacts_folder_delete", "artifacts_move",
        "artifacts_post_comment", "artifacts_reply_comment",
        "artifacts_mark_comment_review",
    )
    for name in deterministic_names:
        assert tools[name].fn._mcp_category == "deterministic"
    for name in operational_names:
        assert tools[name].fn._mcp_category == "operational"
    for name in ("artifacts_resolve_comment", "artifacts_delete_comment",
                 "artifacts_purge"):
        assert tools[name].fn._mcp_category == "authoring"
    saved = await catalog.call_tool("artifacts_save", {
        "name": "MCP Artifact", "content": "body", "idempotency_key": "mcp-1",
    })
    assert saved.structured_content["ok"] is True
    assert saved.structured_content["data"]["result"]["artifact"]["slug"] == "mcp-artifact"
    listed = await catalog.call_tool("artifacts_list", {})
    assert listed.structured_content["ok"] is True
    assert len(listed.structured_content["data"]["artifacts"]) == 1


@pytest.mark.asyncio
async def test_missing_authority_fails_closed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(support, "get_envelope", lambda: {})
    catalog = create_tool_catalog(runtime(tmp_path))
    result = await catalog.call_tool("artifacts_list", {})
    assert result.is_error is True
    assert result.structured_content == {
        "schema_version": "v1", "ok": False, "data": None,
        "error": "tool_execution_failed", "idempotency_key": None,
    }


@pytest.mark.asyncio
async def test_public_version_lifecycle_is_typed_and_opaque(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(support, "get_envelope", lambda: {
        "tenant_id": "tenant", "principal_id": "owner", "agent_id": "agent",
    })
    catalog = create_tool_catalog(runtime(tmp_path))
    created = await catalog.call_tool("artifacts_save", {
        "name": "Lifecycle", "content": "v1",
    })
    slug = created.structured_content["data"]["result"]["artifact"]["slug"]
    updated = await catalog.call_tool("artifacts_update", {
        "slug": slug, "expected_revision": 1, "content": "v2",
        "tags": ["typed"],
    })
    assert updated.structured_content["data"]["result"]["artifact"]["version"] == 2
    versions = await catalog.call_tool("artifacts_versions", {"slug": slug})
    assert [v["version"] for v in versions.structured_content["data"]["versions"]] == [2, 1]
    reverted = await catalog.call_tool("artifacts_revert", {
        "slug": slug, "version": 1, "expected_revision": 2,
    })
    assert reverted.structured_content["data"]["result"]["artifact"]["content"] == "v1"
    removed = await catalog.call_tool("artifacts_tombstone", {
        "slug": slug, "expected_revision": 3,
    })
    assert removed.structured_content["data"]["tombstoned"] is True
    hidden = await catalog.call_tool("artifacts_versions", {"slug": slug})
    assert hidden.is_error is True
    assert hidden.structured_content["error"] == "tool_execution_failed"


@pytest.mark.asyncio
async def test_public_folder_lifecycle_is_typed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(support, "get_envelope", lambda: {
        "tenant_id": "tenant", "principal_id": "owner", "agent_id": "agent",
    })
    catalog = create_tool_catalog(runtime(tmp_path))
    saved = await catalog.call_tool("artifacts_save", {
        "name": "Filed", "content": "body",
    })
    artifact = saved.structured_content["data"]["result"]["artifact"]
    created = await catalog.call_tool("artifacts_folder_create", {"name": "Docs"})
    folder = created.structured_content["data"]["folder"]
    moved = await catalog.call_tool("artifacts_move", {
        "slug": artifact["slug"], "expected_revision": artifact["revision"],
        "folder_id": folder["id"],
    })
    assert moved.structured_content["data"]["artifact"]["folder_id"] == folder["id"]
    listed = await catalog.call_tool("artifacts_folder_list", {})
    assert listed.structured_content["data"]["folders"][0]["item_count"] == 1
    deleted = await catalog.call_tool("artifacts_folder_delete", {
        "folder_id": folder["id"], "expected_revision": folder["revision"],
    })
    assert deleted.structured_content["data"]["deleted"] is True
    reopened = await catalog.call_tool("artifacts_get", {"slug": artifact["slug"]})
    assert reopened.structured_content["data"]["artifact"]["folder_id"] is None

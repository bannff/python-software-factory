from __future__ import annotations

import pytest

from factory.agent.registry.defaults_artifacts import ARTIFACT_CHAT_TOOLS
from factory.artifacts.runtime.adapters.sql import SQLArtifactStore
from factory.artifacts.runtime.lifecycle import ArtifactLifecycle
from factory.artifacts.runtime.runtime import ArtifactsRuntime
from factory.artifacts.server import create_tool_catalog
from factory.mcp_utils.interface import reset_envelope, set_envelope
from factory.storage.runtime.adapters.sql_sqlite import SQLiteSQLStore


def runtime(path) -> ArtifactsRuntime:
    return ArtifactsRuntime(ArtifactLifecycle(SQLArtifactStore(SQLiteSQLStore(str(path)))))


def data(result):
    assert result.structured_content["ok"] is True
    return result.structured_content["data"]


@pytest.mark.asyncio
async def test_exact_chat_artifact_lifecycle_survives_restart(tmp_path) -> None:
    path = tmp_path / "chat-artifacts.db"
    active = runtime(path)
    catalog = create_tool_catalog(active)
    names = {tool.name for tool in await catalog.list_tools()}
    assert set(ARTIFACT_CHAT_TOOLS) <= names
    token = set_envelope({
        "tenant_id": "tenant", "principal_id": "owner",
        "agent_id": "artifact-curator",
    })
    try:
        created = data(await catalog.call_tool("artifacts_save", {
            "name": "Chat report", "content": "version one",
            "idempotency_key": "chat-acceptance",
        }))["result"]["artifact"]
        updated = data(await catalog.call_tool("artifacts_update", {
            "slug": created["slug"], "expected_revision": created["revision"],
            "content": "version two",
        }))["result"]["artifact"]
        before = data(await catalog.call_tool("artifacts_versions", {
            "slug": created["slug"],
        }))["versions"]
        assert [item["version"] for item in before] == [2, 1]
        comment = data(await catalog.call_tool("artifacts_post_comment", {
            "slug": created["slug"], "body": "Restore the concise opening.",
        }))["comment"]
        assert comment["actor_kind"] == "agent"
        reverted = data(await catalog.call_tool("artifacts_revert", {
            "slug": created["slug"], "version": 1,
            "expected_revision": updated["revision"],
        }))["result"]["artifact"]
        assert (reverted["version"], reverted["content"]) == (3, "version one")
        reopened = data(await catalog.call_tool("artifacts_get", {
            "slug": created["slug"],
        }))["artifact"]
        assert reopened == reverted
    finally:
        reset_envelope(token)

    restarted = runtime(path).lifecycle.get("tenant", "owner", created["slug"])
    assert (restarted.version, restarted.content) == (3, "version one")
    assert [item.version for item in runtime(path).lifecycle.versions(
        "tenant", "owner", created["slug"],
    )] == [3, 2, 1]

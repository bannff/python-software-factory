from __future__ import annotations

import pytest
from pydantic import ValidationError

from factory.artifacts.mcp import support
from factory.artifacts.mcp.events import ArtifactEventPayload
from factory.artifacts.runtime.adapters.sql import SQLArtifactStore
from factory.artifacts.runtime.lifecycle import ArtifactLifecycle
from factory.artifacts.runtime.runtime import ArtifactsRuntime
from factory.artifacts.server import create_tool_catalog
from factory.mcp_utils.interface import get_service, set_service
from factory.storage.runtime.adapters.sql_sqlite import SQLiteSQLStore


def runtime(tmp_path) -> ArtifactsRuntime:
    return ArtifactsRuntime(ArtifactLifecycle(
        SQLArtifactStore(SQLiteSQLStore(str(tmp_path / "a.db"))),
    ))


def success_factory(calls):
    def factory(caller):
        assert caller == "artifacts"
        def invoke(target, **kwargs):
            assert target == {"brick_name": "events", "tool_name": "events_publish"}
            calls.append(kwargs)
            return {"ok": True, "result": {"structured_content": {
                "ok": True, "data": {"event_id": "evt"},
            }}}
        return invoke
    return factory


@pytest.mark.asyncio
async def test_events_are_owner_derived_and_content_free(tmp_path, monkeypatch) -> None:
    calls = []
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", success_factory(calls))
    monkeypatch.setattr(support, "get_envelope", lambda: {
        "tenant_id": "tenant", "principal_id": "owner", "agent_id": "agent",
    })
    try:
        catalog = create_tool_catalog(runtime(tmp_path))
        created = await catalog.call_tool("artifacts_save", {
            "name": "Private Name", "content": "private body",
            "description": "private description", "tags": ["private-tag"],
        })
        slug = created.structured_content["data"]["result"]["artifact"]["slug"]
        updated = await catalog.call_tool("artifacts_update", {
            "slug": slug, "expected_revision": 1, "content": "changed private body",
        })
        commented = await catalog.call_tool("artifacts_post_comment", {
            "slug": slug, "body": "private comment body",
        })
        assert created.structured_content["data"]["event_published"] is True
        assert updated.structured_content["data"]["event_published"] is True
        assert commented.structured_content["data"]["event_published"] is True
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert len(calls) == 3
    comment_payload = calls[2]["arguments"]["payload"]
    assert comment_payload["comment_id"] is not None
    assert comment_payload["content_sha256"] is None
    allowed = {"authority", "slug", "version", "revision", "kind",
               "folder_id", "comment_id", "content_sha256"}
    for call in calls:
        payload = call["arguments"]["payload"]
        assert set(payload) <= allowed
        assert payload["authority"] == {
            "tenant_id": "tenant", "principal_id": "owner",
        }
        serialized = repr(payload)
        for secret in ("private body", "Private Name", "private description",
                       "private-tag", "private comment body"):
            assert secret not in serialized


def test_event_payload_rejects_private_fields() -> None:
    with pytest.raises(ValidationError):
        ArtifactEventPayload(
            authority={"tenant_id": "t", "principal_id": "o"},
            slug="doc", version=1, revision=1, kind="text",
            content="private",
        )


@pytest.mark.asyncio
async def test_event_failure_is_truthful_and_does_not_rollback(tmp_path, monkeypatch) -> None:
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", None)
    monkeypatch.setattr(support, "get_envelope", lambda: {
        "tenant_id": "tenant", "principal_id": "owner", "agent_id": "agent",
    })
    try:
        catalog = create_tool_catalog(runtime(tmp_path))
        result = await catalog.call_tool("artifacts_save", {
            "name": "Durable", "content": "body",
        })
        data = result.structured_content["data"]
        assert data["event_published"] is False
        assert data["warning"] == "artifact_event_unavailable"
        listed = await catalog.call_tool("artifacts_list", {})
        assert len(listed.structured_content["data"]["artifacts"]) == 1
    finally:
        set_service("tool_invoker_for_caller", previous)

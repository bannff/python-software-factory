from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from factory.artifacts.mcp import support
from factory.artifacts.runtime.adapters.sql import SQLArtifactStore
from factory.artifacts.runtime.comments import CommentLifecycle
from factory.artifacts.runtime.lifecycle import ArtifactLifecycle
from factory.artifacts.runtime.runtime import ArtifactsRuntime
from factory.artifacts.server import create_tool_catalog
from factory.storage.runtime.adapters.sql_sqlite import SQLiteSQLStore


def services(tmp_path):
    store = SQLArtifactStore(SQLiteSQLStore(str(tmp_path / "a.db")))
    lifecycle = ArtifactLifecycle(store)
    return lifecycle, CommentLifecycle(store), ArtifactsRuntime(lifecycle)


def test_one_level_threads_review_and_tombstone_opacity(tmp_path) -> None:
    artifacts, comments, _ = services(tmp_path)
    artifact = artifacts.save("t", "o", "Doc", "body").artifact
    root = comments.post("t", "o", artifact.slug, "root", "agent")
    reply = comments.post("t", "o", artifact.slug, "reply", "human", root.id)
    assert reply.root_id == root.id and reply.actor_kind == "human"
    with pytest.raises(ValueError, match="not_found_or_limit"):
        comments.post("t", "o", artifact.slug, "nested", "agent", reply.id)
    review = comments.mark_review("t", "o", artifact.slug, root.id)
    assert review.status == "review" and review.revision == 2
    with pytest.raises(PermissionError, match="human actor"):
        comments.resolve("t", "o", artifact.slug, root.id, 2, "agent")
    artifacts.tombstone("t", "o", artifact.slug, artifact.revision)
    with pytest.raises(ValueError, match="artifact_not_found"):
        comments.list("t", "o", artifact.slug)
    with pytest.raises(ValueError, match="artifact_not_found"):
        comments.list("t", "foreign", artifact.slug)


def test_concurrent_comment_cap_stores_exactly_500(tmp_path) -> None:
    artifacts, comments, _ = services(tmp_path)
    artifact = artifacts.save("t", "o", "Doc", "body").artifact
    for index in range(499):
        comments.post("t", "o", artifact.slug, f"comment {index}", "agent")
    workers = [services(tmp_path)[1], services(tmp_path)[1]]
    def final(index: int):
        try:
            return workers[index].post(
                "t", "o", artifact.slug, f"final {index}", "agent",
            )
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(final, range(2)))
    assert sum(result is not None for result in results) == 1
    assert len(comments.list("t", "o", artifact.slug)) == 500


@pytest.mark.asyncio
async def test_authoring_requires_human_and_kill_switch(tmp_path, monkeypatch) -> None:
    artifacts, _, runtime = services(tmp_path)
    artifact = artifacts.save("t", "o", "Doc", "body").artifact
    state = {"tenant_id": "t", "principal_id": "o", "agent_id": "agent"}
    monkeypatch.setattr(support, "get_envelope", lambda: state)
    monkeypatch.setenv("ARTIFACTS_ENABLE_AUTHORING_TOOLS", "true")
    catalog = create_tool_catalog(runtime)
    posted = await catalog.call_tool("artifacts_post_comment", {
        "slug": artifact.slug, "body": "root",
    })
    comment = posted.structured_content["data"]["comment"]
    marked = await catalog.call_tool("artifacts_mark_comment_review", {
        "slug": artifact.slug, "comment_id": comment["id"],
    })
    assert marked.structured_content["data"]["comment"]["status"] == "review"
    denied = await catalog.call_tool("artifacts_resolve_comment", {
        "slug": artifact.slug, "comment_id": comment["id"],
        "expected_revision": 2,
    })
    assert denied.structured_content["error"] == "artifact_human_required"
    delete_denied = await catalog.call_tool("artifacts_delete_comment", {
        "slug": artifact.slug, "comment_id": comment["id"],
        "expected_revision": 2,
    })
    assert delete_denied.structured_content["error"] == "artifact_human_required"
    state.pop("agent_id")
    resolved = await catalog.call_tool("artifacts_resolve_comment", {
        "slug": artifact.slug, "comment_id": comment["id"],
        "expected_revision": 2,
    })
    assert resolved.structured_content["data"]["comment"]["status"] == "resolved"
    deleted = await catalog.call_tool("artifacts_delete_comment", {
        "slug": artifact.slug, "comment_id": comment["id"],
        "expected_revision": 3,
    })
    assert deleted.structured_content["data"]["deleted"] is True
    remaining = await catalog.call_tool("artifacts_get_comments", {
        "slug": artifact.slug,
    })
    assert remaining.structured_content["data"]["comments"] == []


@pytest.mark.asyncio
async def test_human_purge_is_tombstone_only_and_permanent(tmp_path, monkeypatch) -> None:
    artifacts, comments, runtime = services(tmp_path)
    artifact = artifacts.save("t", "o", "Doc", "body").artifact
    comments.post("t", "o", artifact.slug, "root", "human")
    tombstone = artifacts.tombstone("t", "o", artifact.slug, artifact.revision)
    state = {"tenant_id": "t", "principal_id": "o", "agent_id": "agent"}
    monkeypatch.setattr(support, "get_envelope", lambda: state)
    monkeypatch.setenv("ARTIFACTS_ENABLE_AUTHORING_TOOLS", "true")
    catalog = create_tool_catalog(runtime)
    denied = await catalog.call_tool("artifacts_purge", {
        "slug": artifact.slug, "expected_revision": tombstone.revision,
    })
    assert denied.structured_content["error"] == "artifact_human_required"
    assert artifacts.store.get_tombstone("t", "o", artifact.slug) is not None
    state.pop("agent_id")
    purged = await catalog.call_tool("artifacts_purge", {
        "slug": artifact.slug, "expected_revision": tombstone.revision,
    })
    assert purged.structured_content["data"]["deleted"] is True
    assert artifacts.store.get_tombstone("t", "o", artifact.slug) is None
    assert artifacts.store.list_versions("t", "o", artifact.slug) == []


def test_anchored_comment_stores_and_round_trips_the_quoted_span(tmp_path) -> None:
    """Row 65 (Artifact comments): a comment born from a text selection
    carries the exact quoted span so the UI can re-locate it later."""
    artifacts, comments, _ = services(tmp_path)
    artifact = artifacts.save("t", "o", "Doc", "The quick brown fox").artifact
    anchored = comments.post(
        "t", "o", artifact.slug, "typo here", "human",
        anchor_text="quick brown fox",
    )
    assert anchored.anchor_text == "quick brown fox"
    fetched = comments.list("t", "o", artifact.slug)[0]
    assert fetched.anchor_text == "quick brown fox"


def test_comment_without_anchor_defaults_to_none(tmp_path) -> None:
    artifacts, comments, _ = services(tmp_path)
    artifact = artifacts.save("t", "o", "Doc", "body").artifact
    unanchored = comments.post("t", "o", artifact.slug, "general note", "human")
    assert unanchored.anchor_text is None


def test_anchor_text_whitespace_only_normalizes_to_none(tmp_path) -> None:
    artifacts, comments, _ = services(tmp_path)
    artifact = artifacts.save("t", "o", "Doc", "body").artifact
    blank = comments.post(
        "t", "o", artifact.slug, "note", "human", anchor_text="   ",
    )
    assert blank.anchor_text is None


@pytest.mark.asyncio
async def test_mcp_post_comment_accepts_anchor_text(tmp_path, monkeypatch) -> None:
    artifacts, _, runtime = services(tmp_path)
    artifact = artifacts.save("t", "o", "Doc", "Some artifact text").artifact
    state = {"tenant_id": "t", "principal_id": "o"}
    monkeypatch.setattr(support, "get_envelope", lambda: state)
    catalog = create_tool_catalog(runtime)
    posted = await catalog.call_tool("artifacts_post_comment", {
        "slug": artifact.slug, "body": "please reword",
        "anchor_text": "artifact text",
    })
    comment = posted.structured_content["data"]["comment"]
    assert comment["anchor_text"] == "artifact text"

"""Feature-map row 67 — provider-neutral publish/refresh (port + MCP)."""
from __future__ import annotations

import asyncio

import pytest

from factory.artifacts.mcp import support
from factory.artifacts.runtime.adapters.local_publish_provider import LocalPublishProvider
from factory.artifacts.runtime.adapters.sql import SQLArtifactStore
from factory.artifacts.runtime.lifecycle import ArtifactLifecycle
from factory.artifacts.runtime.publish import PublishProviderError, PublishProviderRegistry
from factory.artifacts.runtime.publish_lifecycle import PublishLifecycle
from factory.artifacts.runtime.runtime import ArtifactsRuntime
from factory.artifacts.server import create_tool_catalog
from factory.storage.runtime.adapters.sql_sqlite import SQLiteSQLStore

OWNER = ("tenant", "owner")


def _store(tmp_path) -> SQLArtifactStore:
    return SQLArtifactStore(SQLiteSQLStore(str(tmp_path / "artifacts.db")))


def _runtime(tmp_path) -> ArtifactsRuntime:
    return ArtifactsRuntime(ArtifactLifecycle(_store(tmp_path)))


def _save(runtime: ArtifactsRuntime) -> str:
    result = runtime.lifecycle.save(*OWNER, "Doc", "hello", actor_kind="human")
    return result.artifact.slug


def test_registry_rejects_an_unknown_provider() -> None:
    registry = PublishProviderRegistry({"local": LocalPublishProvider()})
    with pytest.raises(PublishProviderError, match="unknown_publish_provider:ghost"):
        registry.get("ghost")
    assert registry.available() == ("local",)


def test_local_provider_publish_and_refresh_round_trip() -> None:
    provider = LocalPublishProvider()

    async def run():
        from factory.artifacts.runtime.models import ArtifactKind
        from datetime import datetime, timezone
        artifact = _artifact("a1", ArtifactKind.MARKDOWN)
        ref, detail = await provider.publish(artifact)
        assert ref == "local:t:o:a1" and "published at content" in detail
        status, detail2 = await provider.refresh(ref)
        assert status == "published" and "still published" in detail2
    asyncio.run(run())


def test_local_provider_refresh_of_unknown_ref_raises() -> None:
    provider = LocalPublishProvider()
    with pytest.raises(PublishProviderError, match="local_publication_not_found"):
        asyncio.run(provider.refresh("local:missing"))


def test_lifecycle_publish_persists_a_truthful_notice(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    slug = _save(runtime)
    lifecycle = PublishLifecycle(
        runtime.lifecycle.store, PublishProviderRegistry({"local": LocalPublishProvider()}),
    )
    notice = asyncio.run(lifecycle.publish(*OWNER, slug, "local"))
    assert notice.provider == "local" and notice.status == "published"
    assert notice.external_ref == f"local:tenant:owner:{slug}"
    fetched = lifecycle.get(*OWNER, slug, "local")
    assert fetched == notice


def test_lifecycle_publish_unknown_artifact_fails_closed(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    lifecycle = PublishLifecycle(
        runtime.lifecycle.store, PublishProviderRegistry({"local": LocalPublishProvider()}),
    )
    with pytest.raises(ValueError, match="artifact_not_found"):
        asyncio.run(lifecycle.publish(*OWNER, "ghost", "local"))


def test_lifecycle_refresh_never_fabricates_published_on_provider_error(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    slug = _save(runtime)
    lifecycle = PublishLifecycle(
        runtime.lifecycle.store, PublishProviderRegistry({"local": LocalPublishProvider()}),
    )
    asyncio.run(lifecycle.publish(*OWNER, slug, "local"))
    # A fresh provider instance has no memory of the prior publish -> refresh must
    # report unavailable, not silently keep reporting "published".
    lifecycle.registry = PublishProviderRegistry({"local": LocalPublishProvider()})
    refreshed = asyncio.run(lifecycle.refresh(*OWNER, slug, "local"))
    assert refreshed.status == "unavailable" and "refresh_failed" in refreshed.detail


def test_unpublish_removes_the_notice(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    slug = _save(runtime)
    lifecycle = PublishLifecycle(
        runtime.lifecycle.store, PublishProviderRegistry({"local": LocalPublishProvider()}),
    )
    asyncio.run(lifecycle.publish(*OWNER, slug, "local"))
    lifecycle.unpublish(*OWNER, slug, "local")
    with pytest.raises(ValueError, match="publication_not_found"):
        lifecycle.get(*OWNER, slug, "local")


@pytest.mark.asyncio
async def test_mcp_publish_refresh_unpublish_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(support, "get_envelope", lambda: {
        "tenant_id": "tenant", "principal_id": "owner",
    })
    runtime = _runtime(tmp_path)
    slug = _save(runtime)
    catalog = create_tool_catalog(runtime)
    tools = {tool.name: tool for tool in await catalog.list_tools()}

    providers = tools["artifacts_publish_providers"].fn(slug=slug)
    assert providers.ok is True and providers.data.providers == ["local"]

    published = await tools["artifacts_publish"].fn(slug=slug, provider="local")
    assert published.ok is True and published.data.publication.status == "published"

    refreshed = await tools["artifacts_publish_refresh"].fn(slug=slug, provider="local")
    assert refreshed.ok is True and refreshed.data.publication.status == "published"

    fetched = tools["artifacts_get_publication"].fn(slug=slug, provider="local")
    assert fetched.ok is True and fetched.data.publication.external_ref == published.data.publication.external_ref

    unpublished = tools["artifacts_unpublish"].fn(slug=slug, provider="local")
    assert unpublished.ok is True

    gone = tools["artifacts_get_publication"].fn(slug=slug, provider="local")
    assert gone.ok is False and gone.error == "publication_not_found"


@pytest.mark.asyncio
async def test_mcp_publish_unknown_provider_is_a_typed_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(support, "get_envelope", lambda: {
        "tenant_id": "tenant", "principal_id": "owner",
    })
    runtime = _runtime(tmp_path)
    slug = _save(runtime)
    catalog = create_tool_catalog(runtime)
    tools = {tool.name: tool for tool in await catalog.list_tools()}
    result = await tools["artifacts_publish"].fn(slug=slug, provider="ghost")
    assert result.ok is False and "unknown_publish_provider" in result.error


def _artifact(slug: str, kind):
    from datetime import datetime, timezone
    from factory.artifacts.runtime.models import ArtifactRecord
    now = datetime.now(timezone.utc)
    return ArtifactRecord(
        tenant_id="t", owner_id="o", slug=slug, name="Doc", kind=kind,
        content="hello", content_sha256="a" * 64, created_at=now, updated_at=now,
    )

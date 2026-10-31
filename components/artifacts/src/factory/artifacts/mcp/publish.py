"""Typed operational artifact publish tools (feature-map row 67)."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, deterministic, fail, ok, operational
from factory.mcp_utils.registration import typed_tool

from .contracts import ArtifactRefInput
from .contracts_publish import PublicationOutput, PublishInput, PublishProvidersOutput
from .support import authority


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=ArtifactRefInput, output_model=PublishProvidersOutput)
    def artifacts_publish_providers(slug: str) -> ToolResult[PublishProvidersOutput]:
        """List the publish providers this deployment has configured."""
        del slug  # provider availability is deployment-wide, not per-artifact
        runtime = get_runtime()
        return ok(PublishProvidersOutput(providers=list(runtime.publish.registry.available())))

    @typed_tool(mcp)
    @operational(input_model=PublishInput, output_model=PublicationOutput, idempotent=False)
    async def artifacts_publish(
        slug: str, provider: str,
    ) -> ToolResult[PublicationOutput]:
        """Push this artifact to ``provider``; records a truthful publication notice."""
        tenant, owner, _ = authority()
        runtime = get_runtime()
        try:
            notice = await runtime.publish.publish(tenant, owner, slug, provider)
        except ValueError as exc:
            return fail(str(exc))
        return ok(PublicationOutput(publication=notice))

    @typed_tool(mcp)
    @operational(input_model=PublishInput, output_model=PublicationOutput, idempotent=False)
    async def artifacts_publish_refresh(
        slug: str, provider: str,
    ) -> ToolResult[PublicationOutput]:
        """Re-check a prior publish; never fabricates "published" if the provider disagrees."""
        tenant, owner, _ = authority()
        runtime = get_runtime()
        try:
            notice = await runtime.publish.refresh(tenant, owner, slug, provider)
        except ValueError as exc:
            return fail(str(exc))
        return ok(PublicationOutput(publication=notice))

    @typed_tool(mcp)
    @operational(input_model=PublishInput, output_model=PublicationOutput)
    def artifacts_get_publication(
        slug: str, provider: str,
    ) -> ToolResult[PublicationOutput]:
        tenant, owner, _ = authority()
        try:
            notice = get_runtime().publish.get(tenant, owner, slug, provider)
        except ValueError as exc:
            return fail(str(exc))
        return ok(PublicationOutput(publication=notice))

    @typed_tool(mcp)
    @operational(input_model=PublishInput, output_model=PublishProvidersOutput, idempotent=False)
    def artifacts_unpublish(
        slug: str, provider: str,
    ) -> ToolResult[PublishProvidersOutput]:
        tenant, owner, _ = authority()
        runtime = get_runtime()
        try:
            runtime.publish.unpublish(tenant, owner, slug, provider)
        except ValueError as exc:
            return fail(str(exc))
        return ok(PublishProvidersOutput(providers=list(runtime.publish.registry.available())))


__all__ = ["register"]

"""MCP tool: preview a companion-x-v1 bundle for import (row 54 Portability
import half). Read-only — no target brick is written by this tool."""
from __future__ import annotations

from typing import Any, Callable

from pydantic import TypeAdapter, ValidationError

from factory.mcp_utils.interface import ToolResult, fail, get_envelope, ok, operational
from factory.mcp_utils.registration import typed_tool

from ..runtime.bundle_preview import BundlePreviewRuntime, BundlePreviewUnavailable
from ..runtime.receipt_models import Identity
from .bundle_contracts import BundlePreviewInput, BundlePreviewOutput

_IDENTITY = TypeAdapter(Identity)
_ERROR = "migration_preview_bundle_unavailable"


def _authority() -> tuple[str, str]:
    envelope = get_envelope()
    if not isinstance(envelope, dict):
        raise ValueError(_ERROR)
    try:
        return (
            _IDENTITY.validate_python(envelope.get("tenant_id"), strict=True),
            _IDENTITY.validate_python(envelope.get("principal_id"), strict=True),
        )
    except ValidationError as exc:
        raise ValueError(_ERROR) from exc


def register(mcp: Any, get_runtime: Callable[[], BundlePreviewRuntime]) -> None:
    @typed_tool(mcp)
    @operational(input_model=BundlePreviewInput, output_model=BundlePreviewOutput)
    def migration_preview_bundle(
        source: str = "companion-x-v1", bundle_ref: str = "", kinds: list[str] | None = None,
    ) -> ToolResult[BundlePreviewOutput]:
        del source  # strict DTO already locks the adapter name
        try:
            tenant, owner = _authority()
            result = get_runtime().preview(
                tenant, owner, bundle_ref, tuple(kinds) if kinds else None,
            )
            return ok(BundlePreviewOutput(
                source_fingerprint=result.plan.source_fingerprint,
                plan_digest=result.plan.plan_digest, status=result.status,
                reports=result.reports, samples=result.samples,
                unsupported_kinds=result.unsupported_kinds,
            ))
        except (OSError, ValueError, BundlePreviewUnavailable):
            return fail(_ERROR)


__all__ = ["register"]

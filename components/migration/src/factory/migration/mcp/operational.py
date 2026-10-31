"""Read-only operational KiroCrew migration preview."""
from __future__ import annotations

from typing import Any, Callable

from pydantic import TypeAdapter, ValidationError

from factory.mcp_utils.interface import (
    ToolResult, fail, get_envelope, ok, operational,
)
from factory.mcp_utils.registration import typed_tool

from ..runtime.preview import PreviewRuntime, PreviewUnavailable
from ..runtime.receipt_models import Identity
from ..runtime.source_models import SourceKind
from .contracts import PreviewInput, PreviewOutput

_IDENTITY = TypeAdapter(Identity)
_ERROR = "migration_preview_unavailable"


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


def register(mcp: Any, get_runtime: Callable[[], PreviewRuntime]) -> None:
    @typed_tool(mcp)
    @operational(input_model=PreviewInput, output_model=PreviewOutput)
    def migration_preview(
        source: str = "kirocrew-v1", kinds: list[str] | None = None,
    ) -> ToolResult[PreviewOutput]:
        del source  # strict DTO already locks the adapter name
        try:
            tenant, owner = _authority()
            selected = tuple(SourceKind(kind) for kind in (kinds or SourceKind))
            result = get_runtime().preview(tenant, owner, selected)
            return ok(PreviewOutput(
                source_fingerprint=result.plan.source_fingerprint,
                plan_digest=result.plan.plan_digest, status=result.status,
                files=result.manifest.files, reports=result.reports,
                samples=result.samples,
                snapshot_diagnostics=result.snapshot_diagnostics,
            ))
        except (OSError, ValueError, PreviewUnavailable):
            return fail(_ERROR)


__all__ = ["register"]

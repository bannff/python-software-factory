"""MCP tools: export preview (no write) and export (writes the bundle)."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import ToolResult, deterministic, fail, ok, operational
from factory.mcp_utils.registration import typed_tool

from ..runtime.bundle_writer import BundleWriteError, resolve_destination, write_bundle
from ..runtime.export import ExportError, build_bundle
from .contracts import ExportInput, ExportOutput, ExportPreviewInput, ExportPreviewOutput, KindSummary

_PREVIEW_ERROR = "portability_export_preview_unavailable"
_EXPORT_ERROR = "portability_export_unavailable"


def _summaries(bundle: dict[str, Any]) -> list[KindSummary]:
    return [
        KindSummary(kind=kind, count=block["count"], excluded=block["excluded"], digest=block["digest"])
        for kind, block in bundle["kinds"].items()
    ]


def register(mcp: Any) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=ExportPreviewInput, output_model=ExportPreviewOutput)
    def portability_export_preview(kinds: list[str] | None = None) -> ToolResult[ExportPreviewOutput]:
        try:
            bundle = build_bundle(tuple(kinds) if kinds else None)
            return ok(ExportPreviewOutput(
                bundle_version=bundle["bundle_version"], adapter=bundle["adapter"],
                content_digest=bundle["content_digest"], kinds=_summaries(bundle),
            ))
        except ExportError as exc:
            return fail(exc.code)
        except (OSError, ValueError):
            return fail(_PREVIEW_ERROR)

    @typed_tool(mcp)
    @operational(input_model=ExportInput, output_model=ExportOutput)
    def portability_export(
        destination_name: str, kinds: list[str] | None = None,
    ) -> ToolResult[ExportOutput]:
        try:
            bundle = build_bundle(tuple(kinds) if kinds else None)
            destination = resolve_destination(destination_name)
            written = write_bundle(destination, bundle)
            return ok(ExportOutput(
                path=str(destination), bundle_version=bundle["bundle_version"],
                adapter=bundle["adapter"], content_digest=bundle["content_digest"],
                bytes_written=written, kinds=_summaries(bundle),
            ))
        except (ExportError, BundleWriteError) as exc:
            return fail(exc.code)
        except (OSError, ValueError):
            return fail(_EXPORT_ERROR)


__all__ = ["register"]

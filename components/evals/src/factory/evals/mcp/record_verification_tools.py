"""Typed deterministic verification for immutable Evals record pointers."""
from __future__ import annotations

from typing import Any

from pydantic import StrictInt
from factory.mcp_utils.interface import ToolResult, deterministic, get_service

from .contracts.durable import VerifyRecordPointerInput, VerifyRecordPointerOutput
from ..runtime.run_record_verifier import PointerVerificationError, validate_pointer, verify_record_pointer


def _pointer(collection: str, doc_id: str, record_kind: str, schema_version: int, revision: str, content_hash: str) -> dict[str, Any]:
    return {"collection": collection, "doc_id": doc_id, "record_kind": record_kind, "schema_version": schema_version, "revision": revision, "content_hash": content_hash}


def _failure(pointer: dict[str, Any], reason: str) -> VerifyRecordPointerOutput:
    return VerifyRecordPointerOutput(verified=False, reason=reason, pointer=pointer)


def register(mcp: Any) -> None:
    """Register the Evals-owned exact-pointer verification surface."""

    @mcp.tool()
    @deterministic(input_model=VerifyRecordPointerInput, output_model=VerifyRecordPointerOutput)
    def evals_verify_record_pointer(collection: str, doc_id: str, record_kind: str, schema_version: StrictInt = 2, revision: str = "v2", content_hash: str = "") -> ToolResult[VerifyRecordPointerOutput]:
        pointer = _pointer(collection, doc_id, record_kind, schema_version, revision, content_hash)
        try:
            validate_pointer(pointer)
        except PointerVerificationError as exc:
            return _failure(pointer, str(exc))
        invoker = get_service("tool_invoker")
        if invoker is None:
            return _failure(pointer, "no_tool_invoker")
        try:
            response = invoker("storage_doc_get", collection=collection, doc_id=doc_id)
            if isinstance(response, ToolResult):
                if not response.ok or response.data is None:
                    return _failure(pointer, "storage_read_failed")
                payload = response.data
            elif isinstance(response, dict):
                if response.get("ok") is False:
                    return _failure(pointer, "storage_read_failed")
                payload = response.get("data") if response.get("ok") is True else response
            else:
                return _failure(pointer, "storage_read_failed")
            return VerifyRecordPointerOutput(**verify_record_pointer(pointer, payload))
        except PointerVerificationError as exc:
            return _failure(pointer, str(exc))
        except Exception:
            return _failure(pointer, "storage_read_failed")

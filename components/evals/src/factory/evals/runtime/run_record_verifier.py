"""Fail-closed verification for immutable Evals record pointers."""
from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from .run_artifacts import json_safe_copy
from .edge_model_evidence import EdgeModelEvidence
from .run_record_contract import (
    EVALUATION_RUN_RECORD_KIND,
    SCHEMA_VERSION,
    document_id,
    expected_terminal_state,
    record_pointer,
    semantic_content_hash,
)
from .run_record_validation import validate_evaluation_run

_HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
_COLLECTION = "eval_results"


class PointerVerificationError(ValueError):
    """Stable rejection reason for an unverified record pointer."""


def _reject(reason: str) -> None:
    raise PointerVerificationError(reason)


def validate_pointer(pointer: dict[str, Any]) -> None:
    """Validate the complete opaque pointer before any storage read."""
    if pointer.get("collection") != _COLLECTION:
        _reject("unsupported_collection")
    kind = pointer.get("record_kind")
    if not isinstance(kind, str) or expected_terminal_state(kind) is None:
        _reject("unsupported_record_kind")
    version = pointer.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        _reject("unsupported_schema_version")
    if pointer.get("revision") != f"v{version}":
        _reject("unsupported_revision")
    doc_id = pointer.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id:
        _reject("malformed_doc_id")
    content_hash = pointer.get("content_hash")
    if not isinstance(content_hash, str) or _HASH_RE.fullmatch(content_hash) is None:
        _reject("malformed_content_hash")


def _loaded_record(pointer: dict[str, Any], response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        if response.get("computed") is False:
            _reject("uncomputed_storage_response")
        found = response.get("found")
        collection = response.get("collection")
        doc_id = response.get("id")
        record = response.get("data")
        if found is False or response.get("error") == "not_found":
            _reject("missing_record")
    else:
        found = getattr(response, "found", None)
        collection = getattr(response, "collection", None)
        doc_id = getattr(response, "id", None)
        record = getattr(response, "data", None)
        if found is False:
            _reject("missing_record")
    if collection != pointer["collection"]:
        _reject("storage_collection_mismatch")
    if doc_id != pointer["doc_id"]:
        _reject("storage_doc_id_mismatch")
    if not isinstance(record, dict):
        _reject("uncomputed_storage_response")
    return record


def _verify_record(pointer: dict[str, Any], record: dict[str, Any]) -> None:
    run_id = record.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        _reject("malformed_record")
    kind = record.get("record_kind")
    if kind != pointer["record_kind"]:
        _reject("record_kind_mismatch")
    if record.get("schema_version") != pointer["schema_version"]:
        _reject("schema_version_mismatch")
    if record.get("terminal_state") != expected_terminal_state(kind):
        _reject("terminal_state_mismatch")
    if document_id(run_id, kind) != pointer["doc_id"]:
        _reject("record_doc_id_mismatch")
    stored_hash = record.get("content_hash")
    if not isinstance(stored_hash, str) or _HASH_RE.fullmatch(stored_hash) is None:
        _reject("malformed_stored_content_hash")
    if stored_hash != pointer["content_hash"]:
        _reject("content_hash_mismatch")
    try:
        recomputed = semantic_content_hash(record)
    except (TypeError, ValueError):
        _reject("malformed_record")
    if recomputed != stored_hash:
        _reject("tampered_record")
    if record_pointer(pointer["doc_id"], record) != pointer:
        _reject("pointer_mismatch")
    if not isinstance(record.get("summary"), dict):
        _reject("malformed_summary")
    artifacts = record.get("artifacts")
    if isinstance(artifacts, dict) and "edge_model_evidence" in artifacts:
        try:
            EdgeModelEvidence.model_validate(artifacts["edge_model_evidence"])
        except ValidationError:
            _reject("invalid_edge_model_evidence")
    if kind == EVALUATION_RUN_RECORD_KIND:
        try:
            reason = validate_evaluation_run(record)
        except (KeyError, TypeError, ValueError):
            _reject("invalid_evaluation_run")
        if reason:
            _reject("invalid_evaluation_run")


def verify_record_pointer(
    pointer: dict[str, Any], storage_response: Any,
) -> dict[str, Any]:
    """Verify an exact pointer and return its deterministic consumer envelope."""
    validate_pointer(pointer)
    record = _loaded_record(pointer, storage_response)
    _verify_record(pointer, record)
    result: dict[str, Any] = {
        "verified": True,
        "pointer": json_safe_copy(pointer),
        "run_id": record["run_id"],
        "summary": json_safe_copy(record["summary"]),
    }
    if record["record_kind"] == EVALUATION_RUN_RECORD_KIND:
        for field in (
            "case_results", "case_scores", "verdict", "pass_rate", "avg_score",
            "total_cases", "passed_cases", "failed_cases", "evaluators_used",
        ):
            result[field] = json_safe_copy(record[field])
    for field in ("policy_ref", "reviewer_tool_scope", "rubric_digest"):
        if field in record:
            result[field] = json_safe_copy(record[field])
    if "artifact_refs" in record:
        result["artifact_refs"] = json_safe_copy(record["artifact_refs"])
    if "artifacts" in record:
        result["artifacts"] = json_safe_copy(record["artifacts"])
        if isinstance(record["artifacts"], dict):
            evidence = record["artifacts"].get("edge_model_evidence")
            if evidence is not None:
                result["edge_model_evidence"] = json_safe_copy(evidence)
    return result

"""Bounded, host-path-free authoring result projections."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from factory.permissions.authoring_yaml import PolicyYamlError

SAFE_CODES = frozenset({
    "unsafe_policy_path", "policy_read_error", "policy_write_error", "policy_delete_error",
    "policy_not_found", "policy_not_mapping", "policy_validation_error", "policy_bounded_json",
    "policy_size_exceeded", "yaml_input_type", "yaml_encoding_error", "yaml_parse_error",
    "yaml_document_count", "yaml_alias_not_allowed", "yaml_merge_not_allowed", "yaml_budget_exceeded",
    "yaml_depth_exceeded", "yaml_mapping_too_large", "yaml_sequence_too_large",
})
_MESSAGE_BY_TYPE = {
    "missing": "required field", "extra_forbidden": "unexpected field", "string_type": "expected string",
    "dict_type": "expected object", "list_type": "expected array", "literal_error": "invalid value",
    "too_short": "value too short", "too_long": "value too long",
}


def logical_policy_path(path: object) -> str:
    """Return a host-independent relative policy path, never a host path."""
    raw = str(path).replace("\\", "/").rstrip("/")
    if raw == "policies":
        return "policies"
    name = Path(raw).name
    if not name or name in {".", ".."} or any(ord(char) < 32 or ord(char) == 127 for char in name):
        name = "unknown.yaml"
    return f"policies/{name[:256]}"


def _detail_message(error_type: object) -> str:
    return _MESSAGE_BY_TYPE.get(str(error_type), "validation failed")


def sanitized_validation_details(error: Exception) -> list[dict[str, str]]:
    if isinstance(error, PolicyYamlError):
        return [{"location": "document", "type": error.code, "message": "policy document rejected"}]
    if isinstance(error, ValidationError):
        details: list[dict[str, str]] = []
        for item in error.errors()[:8]:
            location = ".".join(str(part) for part in item.get("loc", ()))[:256] or "policy"
            if not location.replace(".", "").replace("[", "").replace("]", "").replace("-", "").isalnum():
                location = "policy"
            details.append({
                "location": location, "type": str(item.get("type", "validation_error"))[:64],
                "message": _detail_message(item.get("type")),
            })
        return details
    return [{"location": "policy", "type": "authoring_error", "message": "policy rejected"}]


def _safe_detail_list(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    output: list[dict[str, str]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        raw_type = item.get("type", "validation_error")
        error_type = str(raw_type)[:64]
        raw_location = item.get("location", "policy")
        location = str(raw_location)[:256]
        if not location.replace(".", "").replace("[", "").replace("]", "").replace("-", "").isalnum():
            location = "policy"
        output.append({"location": location or "policy", "type": error_type, "message": _detail_message(error_type)})
    return output


def sanitized_validation_issue(issue: object) -> dict[str, Any]:
    if not isinstance(issue, dict):
        return {"path": "policies/unknown.yaml", "error": "policy_validation_error", "details": []}
    code = issue.get("error") if isinstance(issue.get("error"), str) else "policy_validation_error"
    if code not in SAFE_CODES:
        code = "policy_validation_error"
    return {
        "path": logical_policy_path(issue.get("path", "unknown.yaml")),
        "error": code,
        "details": _safe_detail_list(issue.get("details")),
    }


__all__ = ["SAFE_CODES", "logical_policy_path", "sanitized_validation_details", "sanitized_validation_issue"]

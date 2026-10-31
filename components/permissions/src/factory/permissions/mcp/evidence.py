"""Safe normalization of provider evidence at the Permissions MCP edge."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from factory.mcp_utils.interface import is_bounded_json

from .contracts import PolicyEvidenceOutput

_MAX_PROVIDER_TEXT = 4_096
_POLICY_KEYS = frozenset({"policy_id", "rule_id", "effect"})
_AWS_POLICY_KEYS = frozenset({"policyId", "ruleId", "effect"})
_ISSUE_KEYS = frozenset({
    "code", "errorCode", "errorDescription", "errorMessage", "message", "type", "description",
})


class EvidenceError(ValueError):
    """Raised when provider evidence cannot be safely represented."""


def _fail(label: str) -> None:
    raise EvidenceError(f"invalid {label} evidence")


def _bounded_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list) or len(value) > 1_024 or not is_bounded_json(value):
        _fail(label)
    return value


def _policy_item(value: object, label: str) -> dict[str, object]:
    if isinstance(value, str):
        if not value or len(value) > 128 or any(ord(char) < 32 or ord(char) == 127 for char in value):
            _fail(label)
        return {"policy_id": value}
    if not isinstance(value, Mapping) or not is_bounded_json(value):
        _fail(label)
    keys = set(value)
    if "policy_id" in value:
        if not keys.issubset(_POLICY_KEYS):
            _fail(label)
        item = {key: value[key] for key in _POLICY_KEYS if key in value}
    elif "policyId" in value:
        if not keys.issubset(_AWS_POLICY_KEYS):
            _fail(label)
        item = {"policy_id": value["policyId"]}
        if "ruleId" in value:
            item["rule_id"] = value["ruleId"]
        if "effect" in value:
            item["effect"] = value["effect"]
    else:
        _fail(label)
    try:
        return PolicyEvidenceOutput.model_validate(item).model_dump(exclude_none=True)
    except Exception as exc:
        raise EvidenceError(f"invalid {label} evidence") from exc


def normalize_policy_evidence(value: object, label: str) -> list[dict[str, object]]:
    """Normalize YAML mappings, AWS policyId mappings, and Cedar string IDs."""
    return [_policy_item(item, label) for item in _bounded_list(value, label)]


def _issue_code(value: str | None, kind: str) -> str:
    text = (value or "").lower()
    if "accessdenied" in text or "forbidden" in text or "unauthorized" in text:
        return "access_denied"
    if "throttl" in text or "rateexceed" in text:
        return "throttled"
    if "validation" in text or "invalid" in text:
        return "validation_error"
    if "internal" in text or "failure" in text:
        return "internal_error"
    return "provider_diagnostic" if kind == "diagnostics" else "provider_error"


def normalize_provider_issues(value: object, kind: str) -> list[dict[str, str]]:
    """Reduce provider messages to stable allowlisted codes, never raw text."""
    if kind not in {"diagnostics", "errors"}:
        raise EvidenceError("invalid provider issue kind")
    output: list[dict[str, str]] = []
    for item in _bounded_list(value, kind):
        if isinstance(item, str):
            if not item or len(item) > _MAX_PROVIDER_TEXT:
                _fail(kind)
            output.append({"code": _issue_code(item, kind)})
            continue
        if not isinstance(item, Mapping) or not is_bounded_json(item) or not item:
            _fail(kind)
        if not set(item).issubset(_ISSUE_KEYS):
            _fail(kind)
        code_value: Any = next(
            (item[key] for key in ("code", "errorCode", "type") if key in item), None,
        )
        if code_value is not None and (not isinstance(code_value, str) or len(code_value) > 256):
            _fail(kind)
        description = next(
            (item[key] for key in ("errorDescription", "errorMessage", "message", "description") if key in item),
            None,
        )
        if description is not None and (not isinstance(description, str) or len(description) > _MAX_PROVIDER_TEXT):
            _fail(kind)
        output.append({"code": _issue_code(code_value, kind)})
    return output


__all__ = ["EvidenceError", "normalize_policy_evidence", "normalize_provider_issues"]

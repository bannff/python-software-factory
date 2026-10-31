"""Generic immutable target resolution for Telemetry materialization."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from factory.mcp_utils.interface import get_service

from .provenance_mapping_models import MappingActivationRecord, MaterializationTarget

TargetResolver = Callable[[MaterializationTarget], Any]


def validate_activation_targets(
    record: MappingActivationRecord,
    resolver: TargetResolver | None = None,
) -> MappingActivationRecord:
    """Reject an activation whose immutable brick/capability/version is unresolved."""
    for mapping in record.mappings:
        target = MaterializationTarget(
            brick_name=mapping.target_brick,
            capability=mapping.target_capability,
            version=mapping.target_version,
        )
        resolved = resolver(target) if resolver is not None else resolve_target(target)
        if not _matches_target(resolved, target):
            raise ValueError(
                f"unresolved materialization target: {target.brick_name}/"
                f"{target.capability}@{target.version}"
            )
    return record


def resolve_target(target: MaterializationTarget) -> Any:
    """Resolve through registered capability discovery and native invocation."""
    custom = get_service("provenance_target_resolver")
    if callable(custom):
        try:
            return custom(target)
        except Exception:
            return None

    tools = get_service("brick_tools")
    invoker = get_service("tool_invoker_envelope")
    if not callable(tools) or not callable(invoker):
        return None
    try:
        schema = tools(target.brick_name)
        if not _has_capability(schema, target):
            return None
        result = invoker(
            {"brick_name": target.brick_name, "tool_name": "get_capabilities",
             "version": target.version},
            arguments={},
            idempotency_key=f"telemetry-resolve:{target.brick_name}:{target.version}",
            envelope={},
        )
        if invocation_failure(result) is not None:
            return None
        return _success_payload(result)
    except Exception:
        return None


def invocation_failure(result: Any) -> str | None:
    """Normalize typed, native transport, and legacy ``{"error": ...}`` failures."""
    if hasattr(result, "model_dump"):
        result = result.model_dump(mode="json")
    if result is None:
        return "empty_invocation_result"
    if not isinstance(result, Mapping):
        return None if getattr(result, "ok", True) else "invocation_failed"
    if result.get("ok") is False:
        return _error_text(result.get("error"))
    if result.get("error") not in (None, ""):
        return _error_text(result.get("error"))
    for key in ("structured_content", "result"):
        if key in result:
            failure = invocation_failure(result[key])
            if failure is not None:
                return failure
    return None


def _success_payload(result: Any) -> Any:
    if hasattr(result, "model_dump"):
        result = result.model_dump(mode="json")
    if not isinstance(result, Mapping):
        return result
    if "structured_content" in result:
        return _success_payload(result["structured_content"])
    if "result" in result:
        return _success_payload(result["result"])
    if result.get("ok") is True and "data" in result:
        return _success_payload(result["data"])
    return result


def _matches_target(result: Any, target: MaterializationTarget) -> bool:
    if result is True:
        return True
    if isinstance(result, str):
        return result == target.version
    payload = _success_payload(result)
    if isinstance(payload, Mapping):
        version = payload.get("version") or payload.get("target_version")
        return version == target.version
    return False


def _has_capability(schema: Any, target: MaterializationTarget) -> bool:
    if not isinstance(schema, Mapping):
        return False
    names = {
        target.capability,
        f"{target.brick_name}_{target.capability}",
        f"{target.brick_name}.{target.capability}",
    }
    return any(
        isinstance(item, Mapping) and item.get("name") in names
        for item in schema.get("tools", [])
    )


def _error_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("message") or value.get("type") or json.dumps(value, sort_keys=True))
    return str(value or "invocation_failed")


__all__ = ["TargetResolver", "invocation_failure", "resolve_target", "validate_activation_targets"]

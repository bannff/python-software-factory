"""Cedar policy evaluator adapter — implements PolicyEvaluator Protocol."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .cedar import CedarAdapter, CedarEvalRequest

_ENTITY_TYPE_RE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*::)*[A-Za-z_][A-Za-z0-9_]*")


def _cedar_string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Invalid Cedar {label}")
    try:
        return json.dumps(value, ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid Cedar {label}") from exc


def _cedar_entity(entity_type: object, entity_id: object, label: str) -> str:
    if not isinstance(entity_type, str) or _ENTITY_TYPE_RE.fullmatch(entity_type) is None:
        raise ValueError("Invalid Cedar entity type")
    return f"{entity_type}::{_cedar_string(entity_id, label)}"


class CedarEvaluatorAdapter:
    """Cedar evaluator behind the PolicyEvaluator port."""

    def __init__(self, policies_dir: Path | None = None) -> None:
        self._cedar = CedarAdapter(policies_dir)

    def evaluate(
        self, *, action: str, resource: dict[str, Any], context: dict[str, Any],
        principal_id: str | None = None, tenant_id: str | None = None,
    ) -> dict[str, Any]:
        principal = _cedar_entity("User", principal_id or "anonymous", "principal_id")
        cedar_action = _cedar_entity("Action", action, "action")
        res_type = resource.get("type", "Resource")
        res_id = resource.get("id", "unknown")
        cedar_resource = _cedar_entity(res_type, res_id, "resource_id")
        result = self._cedar.evaluate(CedarEvalRequest(
            principal=principal, action=cedar_action, resource=cedar_resource, context=context,
        ))
        return {
            "decision": result.decision,
            "diagnostics": result.diagnostics,
            "determining_policies": result.determining_policies,
        }

    def explain(
        self, *, action: str, resource: dict[str, Any], context: dict[str, Any],
        principal_id: str | None = None, tenant_id: str | None = None,
    ) -> dict[str, Any]:
        result = self.evaluate(
            action=action, resource=resource, context=context,
            principal_id=principal_id, tenant_id=tenant_id,
        )
        result["trace_id"] = "cedar"
        result["matched_rules"] = result.get("determining_policies", [])
        return result

    def health_check(self) -> dict[str, Any]:
        return self._cedar.health_check()


__all__ = ["CedarEvaluatorAdapter"]

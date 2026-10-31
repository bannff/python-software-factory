"""AWS Verified Permissions adapter — implements PolicyEvaluator Protocol."""
from __future__ import annotations

import re
import time
from typing import Any

_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,200}$")


def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        raise ImportError("boto3 is required for Verified Permissions adapter") from None


def _validate_id(value: str, label: str = "identifier") -> str:
    if (
        not isinstance(value, str)
        or _SAFE_ID.fullmatch(value) is None
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError(f"Invalid {label}")
    return value


class AWSVerifiedPermissionsAdapter:
    """Amazon Verified Permissions evaluator behind the PolicyEvaluator port."""

    def __init__(self, policy_store_id: str, region: str = "us-east-1") -> None:
        _require_boto3()
        import boto3
        self._policy_store_id = _validate_id(policy_store_id, "policy_store_id")
        self._region = region
        self._client = boto3.client("verifiedpermissions", region_name=region)

    def _build_request(
        self, *, action: str, resource: dict[str, Any], context: dict[str, Any],
        principal_id: str | None = None, tenant_id: str | None = None,
    ) -> dict[str, Any]:
        res_type = resource.get("type", "Resource")
        res_id = resource.get("id", "unknown")
        req: dict[str, Any] = {
            "policyStoreId": self._policy_store_id,
            "action": {"actionType": "Action", "actionId": action},
            "resource": {"entityType": res_type, "entityId": res_id},
        }
        if principal_id:
            req["principal"] = {"entityType": "User", "entityId": principal_id}
        if context or tenant_id:
            ctx = {**context}
            if tenant_id:
                ctx["tenant_id"] = tenant_id
            req["context"] = {"contextMap": {key: {"string": str(value)} for key, value in ctx.items()}}
        return req

    def evaluate(
        self, *, action: str, resource: dict[str, Any], context: dict[str, Any],
        principal_id: str | None = None, tenant_id: str | None = None,
    ) -> dict[str, Any]:
        resp = self._client.is_authorized(**self._build_request(
            action=action, resource=resource, context=context,
            principal_id=principal_id, tenant_id=tenant_id,
        ))
        return {
            "decision": "allow" if resp.get("decision") == "ALLOW" else "deny",
            "determining_policies": resp.get("determiningPolicies", []),
        }

    def explain(
        self, *, action: str, resource: dict[str, Any], context: dict[str, Any],
        principal_id: str | None = None, tenant_id: str | None = None,
    ) -> dict[str, Any]:
        resp = self._client.is_authorized(**self._build_request(
            action=action, resource=resource, context=context,
            principal_id=principal_id, tenant_id=tenant_id,
        ))
        return {
            "decision": "allow" if resp.get("decision") == "ALLOW" else "deny",
            "determining_policies": resp.get("determiningPolicies", []),
            "errors": resp.get("errors", []),
            "trace_id": "verified-permissions",
            "matched_rules": [p.get("policyId", "") for p in resp.get("determiningPolicies", [])],
        }

    def health_check(self) -> dict[str, Any]:
        start = time.time()
        try:
            self._client.get_policy_store(policyStoreId=self._policy_store_id)
            return {
                "healthy": True, "backend": "verified-permissions",
                "policy_store_id": self._policy_store_id,
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
        except Exception as e:
            return {
                "healthy": False, "backend": "verified-permissions",
                "message": str(e),
            }

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "service": "verifiedpermissions", "construct": "PolicyStore",
            "props": {"validation_settings": {"mode": "STRICT"}},
        }


__all__ = ["AWSVerifiedPermissionsAdapter", "_validate_id"]

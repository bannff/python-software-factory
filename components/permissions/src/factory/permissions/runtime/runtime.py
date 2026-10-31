"""Permissions runtime.

Loads policies from YAML, selects an evaluator adapter (YAML or Cedar)
based on configuration, records audit entries, and exposes Cedar as an
optional secondary evaluator via the CedarMixin.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .audit import AuditEntry, AuditStore, InMemoryAuditStore
from .cedar_mixin import CedarMixin
from .envelope import Envelope
from .evaluation.yaml_adapter import YamlEvaluatorAdapter
from .models import PolicyDefinition, Resource, Settings
from .roles import RoleRegistry


class PermissionsRuntime(CedarMixin):
    def __init__(self, config_dir: str | Path):
        self._config_dir = Path(config_dir)
        self._settings = self._load_settings()
        self._policies: list[PolicyDefinition] = self._load_policies()
        self._roles = RoleRegistry(self._config_dir)
        self._audit_store: AuditStore = InMemoryAuditStore()
        self._evaluator = self._create_evaluator()
        self._init_cedar()

    @classmethod
    def from_config_dir(cls, config_dir: str | Path) -> PermissionsRuntime:
        return cls(config_dir)

    def set_audit_store(self, store: AuditStore) -> None:
        self._audit_store = store

    def get_role_registry(self) -> list[dict[str, Any]]:
        return self._roles.as_list()

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "tools": {
                "deterministic": [
                    "permissions.get_capabilities",
                    "permissions.health_check",
                    "permissions.describe_config_schema",
                    "permissions.get_role_registry",
                    "permissions.get_policy_registry",
                ],
                "operational": [
                    "permissions.evaluate",
                    "permissions.batch_evaluate",
                    "permissions.explain",
                ],
            },
            "cedar_enabled": self._cedar is not None,
        }

    def evaluate(
        self,
        *,
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any] | None = None,
        envelope: Envelope | None = None,
    ) -> dict[str, Any]:
        context = context or {}
        envelope = envelope or Envelope()

        result = self._evaluator.evaluate(
            action=action,
            resource=resource,
            context=context,
            principal_id=envelope.principal_id,
            tenant_id=envelope.tenant_id,
        )

        resource_obj = Resource.model_validate(resource)
        self._audit_store.log(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                action=action,
                resource_type=resource_obj.type,
                resource_id=resource_obj.id,
                decision=result["decision"],
                reason=result.get("reason"),
                principal_id=envelope.principal_id,
                tenant_id=envelope.tenant_id,
                policy_id=result.get("policy_id"),
                rule_id=result.get("rule_id"),
                context=context,
            )
        )
        return result

    def batch_evaluate(
        self,
        *,
        requests: list[dict[str, Any]],
        envelope: Envelope | None = None,
    ) -> list[dict[str, Any]]:
        envelope = envelope or Envelope()
        return [
            self.evaluate(
                action=req["action"],
                resource=req["resource"],
                context=req.get("context") or {},
                envelope=envelope,
            )
            for req in requests
        ]

    def explain(
        self,
        *,
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any] | None = None,
        envelope: Envelope | None = None,
    ) -> dict[str, Any]:
        context = context or {}
        envelope = envelope or Envelope()
        return self._evaluator.explain(
            action=action,
            resource=resource,
            context=context,
            principal_id=envelope.principal_id,
            tenant_id=envelope.tenant_id,
        )

    def get_policies(self) -> list[PolicyDefinition]:
        return list(self._policies)

    # ---- internal ----

    def _create_evaluator(self) -> YamlEvaluatorAdapter:
        """Create the policy evaluator based on settings.

        Supported evaluator kinds:
        - ``yaml`` (default): Local YAML-based policy evaluation.
        - ``aws``: AWS Verified Permissions (requires ``policy_store_id``
          and optional ``region`` in settings).

        When Cedar is configured as the *primary* backend (not just the
        mixin), a ``CedarEvaluatorAdapter`` can be returned instead.
        """
        evaluator_kind = getattr(self._settings, "evaluator", "yaml")
        if evaluator_kind == "aws":
            from .evaluation.aws import AWSVerifiedPermissionsAdapter
            policy_store_id = getattr(self._settings, "policy_store_id", "")
            region = getattr(self._settings, "region", "us-east-1")
            return AWSVerifiedPermissionsAdapter(policy_store_id=policy_store_id, region=region)  # type: ignore[return-value]
        return YamlEvaluatorAdapter(self._policies)

    def _load_settings(self) -> Settings:
        settings_path = self._config_dir / "settings.yaml"
        if not settings_path.exists():
            return Settings()
        data = yaml.safe_load(settings_path.read_text())
        if not isinstance(data, dict):
            return Settings()
        try:
            return Settings.model_validate(data)
        except Exception:
            return Settings()

    def _load_policies(self) -> list[PolicyDefinition]:
        policies_dir = self._config_dir / self._settings.policy_store.policies_subdir
        if not policies_dir.exists():
            return []
        from .storage.filesystem import FilesystemPolicyStore

        store = FilesystemPolicyStore(
            self._config_dir, self._settings.policy_store.policies_subdir,
        )
        policies = store.load_policies()
        health = store.health_check()
        if not health.get("ok"):
            raise ValueError("permissions policy set is unavailable")
        return policies

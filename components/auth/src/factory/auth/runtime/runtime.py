"""Reusable Auth runtime without MCP transport dependencies."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import RootModel

from factory.auth.runtime.models import KeycloakBackendConfig, SCHEMA_VERSION, Settings
from factory.auth.runtime.ports import AuthBackend, WorkloadCredentialProvider
from factory.auth.runtime.workload_credentials import DisabledWorkloadCredentialProvider
from factory.auth.runtime.workload_models import (
    AccessCredential, IssuedWorkloadCredential, WorkloadGrant,
)
from factory.auth.runtime import operations as ops


def create_auth_backend(
    backend_type: str = "memory",
    *,
    config: KeycloakBackendConfig | None = None,
) -> AuthBackend:
    """Factory function to create authentication backends.
    
    Args:
        backend_type: Type of backend ("memory", "keycloak", "authlib_keycloak", or "aws")
        config: Configuration for the backend (required for keycloak and aws)
    
    Returns:
        An AuthBackend implementation
    """
    from factory.auth.runtime.adapters import create_backend
    return create_backend(backend_type, config=config)


class AuthRuntime:
    """Reusable auth runtime (no FastMCP imports)."""

    def __init__(self, config_dir: Path, *,
                 workload_credentials: WorkloadCredentialProvider | None = None):
        self.config_dir = config_dir
        self.workload_credentials = workload_credentials or DisabledWorkloadCredentialProvider()
        self.settings: Settings | None = None
        self.settings_raw: dict[str, Any] | None = None
        self._backend: AuthBackend | None = None
        self._last_backend_error: str | None = None
        self._runtime_authoring_enabled: bool = False
        self._runtime_running_mode: str = "stdio"
        self.initialize()

    def initialize(self) -> None:
        self.settings_raw = self._read_settings_raw()
        self.settings = Settings.model_validate(self.settings_raw)
        try:
            self._backend = self._load_backend(self.settings.backend)
            self._last_backend_error = None
        except Exception as e:
            self._backend = None
            self._last_backend_error = f"{type(e).__name__}: {e}"

    def _read_settings_raw(self) -> dict[str, Any]:
        path = self.config_dir / "settings.yaml"
        if not path.exists():
            raise ValueError(f"Missing settings.yaml in {self.config_dir}")
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict):
            raise ValueError("settings.yaml must parse to a mapping")
        return data

    def _read_backend_raw(self, backend_name: str) -> dict[str, Any]:
        path = self.config_dir / "backends" / f"{backend_name}.yaml"
        if not path.exists():
            raise ValueError(f"Missing backend config: {path}")
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict):
            raise ValueError("backend config must parse to a mapping")
        return data

    def _load_backend(self, backend_name: str) -> AuthBackend:
        raw = self._read_backend_raw(backend_name)
        kind = raw.get("kind")
        if kind == "keycloak":
            cfg = KeycloakBackendConfig.model_validate(raw)
            return create_auth_backend("keycloak", config=cfg)
        if kind == "authlib_keycloak":
            cfg = KeycloakBackendConfig.model_validate(raw)
            return create_auth_backend("authlib_keycloak", config=cfg)
        if kind == "memory":
            return create_auth_backend("memory")
        if kind == "aws" or kind == "cognito":
            return create_auth_backend("aws", config=raw)
        raise ValueError(f"Unsupported backend kind: {kind}")

    def set_runtime_flags(self, *, authoring_enabled: bool, running_mode: str) -> None:
        self._runtime_authoring_enabled = bool(authoring_enabled)
        self._runtime_running_mode = str(running_mode)

    def get_capabilities(self) -> dict[str, Any]:
        assert self.settings is not None
        return {
            "module": "auth-module", "version": "0.2.0",
            "supported_backends": ["keycloak", "authlib_keycloak", "aws"],
            "supported_config_schema_versions": [SCHEMA_VERSION],
            "authoring_enabled": bool(self._runtime_authoring_enabled),
            "running_mode": str(self._runtime_running_mode),
            "feature_flags": {
                "keycloak": True, "jwks": True, "introspection": True,
                "token_refresh": True, "token_revoke": True, "token_exchange": True,
                "userinfo": True, "authoring": bool(self._runtime_authoring_enabled),
            },
            "tools": {
                "deterministic": ["auth.get_capabilities", "auth.health_check", "auth.describe_config_schema"],
                "operational": [
                    "auth.verify_access_token", "auth.introspect_token", "auth.resolve_principal",
                    "auth.refresh_token", "auth.revoke_token", "auth.get_user_info", "auth.exchange_token",
                ],
                "authoring": [
                    "auth.authoring.get_status", "auth.authoring.validate_backend_config",
                    "auth.authoring.upsert_backend_config", "auth.authoring.delete_backend_config",
                ],
            },
        }

    def health_check(self) -> dict[str, Any]:
        assert self.settings is not None
        last_error: str | None = self._last_backend_error
        connectivity = {"attempted": False, "ok": None}
        if self._backend is not None:
            connectivity = self._backend.health_check()
            if connectivity.get("ok") is False:
                last_error = connectivity.get("error")
        return {
            "service_name": self.settings.service_name,
            "backend_selected": self.settings.backend,
            "backend_connectivity": connectivity,
            "last_backend_error": last_error,
        }

    def describe_config_schema(self) -> dict[str, Any]:
        class BackendFile(RootModel[KeycloakBackendConfig]):
            pass
        return {
            "schema_version": SCHEMA_VERSION,
            "schemas": {
                "settings": Settings.model_json_schema(),
                "backend_keycloak": KeycloakBackendConfig.model_json_schema(),
                "backend_file": BackendFile.model_json_schema(),
            },
        }

    def issue_workload_credential(
        self, grant: WorkloadGrant, *, workflow_run_id: str,
        attempt_id: str, revision: int,
    ) -> IssuedWorkloadCredential | AccessCredential:
        return self.workload_credentials.issue(
            grant, workflow_run_id=workflow_run_id,
            attempt_id=attempt_id, revision=revision,
        )

    def revoke_workload_credential(
        self, credential_id: str, *, workflow_run_id: str,
        attempt_id: str, revision: int, manifest_digest: str,
    ) -> bool:
        return self.workload_credentials.revoke(
            credential_id, workflow_run_id=workflow_run_id,
            attempt_id=attempt_id, revision=revision,
            manifest_digest=manifest_digest,
        )

    # Operational surface (delegated)
    def verify_access_token(self, *, token: str, required_audience: str | None,
                            required_scopes: list[str] | None, envelope: dict[str, Any] | None) -> dict[str, Any]:
        return ops.verify_access_token(self._backend, token=token, required_audience=required_audience,
                                        required_scopes=required_scopes, envelope=envelope)

    def introspect_token(self, *, token: str, envelope: dict[str, Any] | None) -> dict[str, Any]:
        return ops.introspect_token(self._backend, token=token, envelope=envelope)

    def resolve_principal(self, *, envelope: dict[str, Any] | None) -> dict[str, Any]:
        return ops.resolve_principal(self._backend, envelope=envelope)

    def refresh_token(self, *, refresh_token: str, scope: str | None = None,
                      envelope: dict[str, Any] | None) -> dict[str, Any]:
        return ops.refresh_token(self._backend, refresh_token=refresh_token, scope=scope, envelope=envelope)

    def revoke_token(self, *, token: str, token_type_hint: str | None = None,
                     envelope: dict[str, Any] | None) -> dict[str, Any]:
        return ops.revoke_token(self._backend, token=token, token_type_hint=token_type_hint, envelope=envelope)

    def get_user_info(self, *, access_token: str, envelope: dict[str, Any] | None) -> dict[str, Any]:
        return ops.get_user_info(self._backend, access_token=access_token, envelope=envelope)

    def exchange_token(self, *, subject_token: str, subject_token_type: str,
                       requested_token_type: str | None = None, audience: str | None = None,
                       scope: str | None = None, envelope: dict[str, Any] | None) -> dict[str, Any]:
        return ops.exchange_token(self._backend, subject_token=subject_token, subject_token_type=subject_token_type,
                                   requested_token_type=requested_token_type, audience=audience,
                                   scope=scope, envelope=envelope)

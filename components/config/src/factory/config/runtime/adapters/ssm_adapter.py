"""AWS SSM Parameter Store config adapter."""

from __future__ import annotations

import importlib.util
import time
from typing import Any

from factory.config.runtime.ports import ConfigHealth

BOTO3_AVAILABLE = importlib.util.find_spec("boto3") is not None


def _require_boto3() -> None:
    if not BOTO3_AVAILABLE:
        raise ImportError("boto3 required. Install with: pip install boto3")


class SSMConfigStore:
    """AWS SSM Parameter Store implementation of ConfigStore port."""

    def __init__(
        self,
        prefix: str = "/factory/",
        region: str = "us-east-1",
        **kwargs: Any,
    ) -> None:
        _require_boto3()
        import boto3
        self._prefix = prefix if prefix.endswith("/") else f"{prefix}/"
        self._client = boto3.client("ssm", region_name=region, **kwargs)
        self._cache: dict[str, Any] = {}

    def _key(self, key: str) -> str:
        """Convert key to SSM parameter name."""
        return f"{self._prefix}{key.replace('.', '/')}"

    def _from_ssm_key(self, ssm_key: str) -> str:
        """Convert SSM parameter name back to config key."""
        return ssm_key[len(self._prefix):].replace("/", ".")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from SSM."""
        try:
            response = self._client.get_parameter(
                Name=self._key(key),
                WithDecryption=True,
            )
            return response["Parameter"]["Value"]
        except self._client.exceptions.ParameterNotFound:
            return default
        except Exception:
            return default

    def get_typed(self, key: str, value_type: type, default: Any = None) -> Any:
        """Get a configuration value with type coercion."""
        value = self.get(key)
        if value is None:
            return default
        try:
            if value_type == bool:
                return str(value).lower() in ("true", "1", "yes", "on")
            return value_type(value)
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: Any, secure: bool = False) -> bool:
        """Set a configuration value in SSM."""
        try:
            self._client.put_parameter(
                Name=self._key(key),
                Value=str(value),
                Type="SecureString" if secure else "String",
                Overwrite=True,
            )
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete a configuration key from SSM."""
        try:
            self._client.delete_parameter(Name=self._key(key))
            return True
        except self._client.exceptions.ParameterNotFound:
            return False
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        """Check if a configuration key exists in SSM."""
        try:
            self._client.get_parameter(Name=self._key(key))
            return True
        except self._client.exceptions.ParameterNotFound:
            return False
        except Exception:
            return False

    def keys(self, prefix: str = "") -> list[str]:
        """List configuration keys with optional prefix filter."""
        try:
            full_prefix = f"{self._prefix}{prefix.replace('.', '/')}"
            paginator = self._client.get_paginator("describe_parameters")
            keys = []
            for page in paginator.paginate(
                ParameterFilters=[{"Key": "Name", "Option": "BeginsWith", "Values": [full_prefix]}]
            ):
                for param in page["Parameters"]:
                    keys.append(self._from_ssm_key(param["Name"]))
            return keys
        except Exception:
            return []

    def get_all(self, prefix: str = "") -> dict[str, Any]:
        """Get all configuration values with optional prefix filter."""
        return {key: self.get(key) for key in self.keys(prefix)}

    def health_check(self) -> ConfigHealth:
        """Check SSM config health."""
        start = time.time()
        try:
            self._client.describe_parameters(MaxResults=1)
            latency = (time.time() - start) * 1000
            return ConfigHealth(
                healthy=True, backend="ssm", latency_ms=latency,
                details={"prefix": self._prefix},
            )
        except Exception as e:
            return ConfigHealth(healthy=False, backend="ssm", message=str(e))

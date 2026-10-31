"""Config runtime factory - selects and configures config adapters.

Usage:
    runtime = ConfigRuntime()
    config = runtime.get_config("env")  # or "file", "ssm"
"""

from __future__ import annotations

import logging
from typing import Any

from .adapters.aws_identity import AWSIdentity, AWSIdentityProbe
from .ports import ConfigStore

logger = logging.getLogger(__name__)


class ConfigRuntime:
    """Factory for creating config adapters."""

    def __init__(self, environment: str = "development") -> None:
        self._environment = environment
        self._configs: dict[str, ConfigStore] = {}
        self._layers: list[ConfigStore] = []  # For layered config
        self._aws_probe: AWSIdentityProbe | None = None
        self._bootstrapped: bool = False

    def get_config(self, backend: str = "env", **kwargs: Any) -> ConfigStore:
        """Get or create a config adapter."""
        cache_key = f"{backend}:{hash(frozenset(kwargs.items()))}"
        if cache_key not in self._configs:
            self._configs[cache_key] = self._create_config(backend, **kwargs)
        return self._configs[cache_key]

    def add_layer(self, config: ConfigStore) -> None:
        """Add a config layer. Later layers override earlier ones."""
        self._layers.append(config)

    def get_layered(self, key: str, default: Any = None) -> Any:
        """Get a value from layered configs (last layer wins).

        On first call, auto-bootstraps SSM + InfraEnv layers so bricks
        can resolve infrastructure settings without manual setup.
        """
        if not self._bootstrapped:
            self._bootstrap()
        for layer in reversed(self._layers):
            if layer.exists(key):
                return layer.get(key)
        return default

    def _bootstrap(self) -> None:
        """Auto-add SSM (best-effort) and InfraEnv layers on first access."""
        self._bootstrapped = True

        # Layer 1 (lowest priority): SSM — reads /art/support/* params
        ssm = None
        try:
            from .adapters.ssm_adapter import SSMConfigStore
            ssm = SSMConfigStore(prefix="/art/support/", region="us-east-1")
            # Smoke test: call GetParameter on a sentinel key. This uses
            # ssm:GetParameter (granted in IAM) instead of DescribeParameters
            # (which requires ssm:DescribeParameters — often not granted).
            # ParameterNotFound is fine — it means SSM is reachable.
            ssm._client.get_parameter(Name="/art/support/neo4j/uri", WithDecryption=True)
            self.add_layer(ssm)
            logger.info("Config bootstrap: SSM layer added (prefix=/art/support/)")
        except Exception as e:
            # SSM is reachable but param doesn't exist — still add the layer
            if ssm is not None and e.__class__.__name__ == "ParameterNotFound":
                self.add_layer(ssm)
                logger.info("Config bootstrap: SSM layer added (prefix=/art/support/)")
            else:
                logger.info("Config bootstrap: SSM layer skipped (%s)", e)

        # Layer 2 (highest priority): InfraEnv — reads NEO4J_URI, GRAPH_BACKEND, etc.
        from .adapters.infra_env import InfraEnvConfigStore
        self.add_layer(InfraEnvConfigStore())
        logger.info("Config bootstrap: InfraEnv layer added")

    def get_aws_identity(self, force: bool = False) -> AWSIdentity:
        """Get the active AWS identity (cached with TTL)."""
        if self._aws_probe is None:
            self._aws_probe = AWSIdentityProbe()
        return self._aws_probe.probe(force=force)

    def _create_config(self, backend: str, **kwargs: Any) -> ConfigStore:
        """Create a config adapter."""
        if backend == "env":
            from .adapters.env_adapter import EnvConfigStore
            return EnvConfigStore(**kwargs)
        elif backend == "file":
            from .adapters.file_adapter import FileConfigStore
            return FileConfigStore(**kwargs)
        elif backend == "ssm":
            from .adapters.ssm_adapter import SSMConfigStore
            return SSMConfigStore(**kwargs)
        elif backend == "pydantic":
            from .adapters.pydantic_adapter import PydanticSettingsStore
            return PydanticSettingsStore(**kwargs)
        raise ValueError(f"Unknown config backend: {backend}. Available: env, file, ssm, pydantic")

    def health_check(self) -> dict[str, Any]:
        """Check health of all active configs.
        
        Returns empty dict if no configs initialized, otherwise
        returns {name: ConfigHealth} for each active config.
        """
        if not self._configs:
            return {}
        return {name: config.health_check() for name, config in self._configs.items()}

    @property
    def environment(self) -> str:
        """Get the current environment."""
        return self._environment

    @property
    def sources(self) -> list[str]:
        """List active config source names."""
        return list(self._configs.keys())

    @staticmethod
    def available_backends() -> list[str]:
        """List available config backends."""
        return ["env", "file", "ssm", "pydantic"]


# Global runtime instance
_runtime: ConfigRuntime | None = None


def get_runtime() -> ConfigRuntime:
    """Get the global config runtime."""
    global _runtime
    if _runtime is None:
        import os
        env = os.environ.get("FACTORY_ENV", "development")
        _runtime = ConfigRuntime(environment=env)
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (for testing)."""
    global _runtime
    _runtime = None

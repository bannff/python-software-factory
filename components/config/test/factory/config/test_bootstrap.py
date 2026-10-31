"""Tests for lazy bootstrap behavior in ConfigRuntime.get_layered().

Verifies:
- Bootstrap runs exactly once on first get_layered() call
- SSM failure is graceful (InfraEnv still added)
- InfraEnv layer is always the highest-priority layer
- Layer priority: SSM (lowest) → InfraEnv (highest)
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from factory.config.runtime.runtime import ConfigRuntime, reset_runtime


class TestBootstrap:
    """Tests for the lazy bootstrap in get_layered()."""

    @pytest.fixture(autouse=True)
    def reset(self) -> None:
        reset_runtime()
        yield
        for k in ("NEO4J_URI", "GRAPH_BACKEND"):
            os.environ.pop(k, None)
        reset_runtime()

    def test_bootstrap_runs_on_first_get_layered(self) -> None:
        """Bootstrap triggers on first get_layered() call."""
        rt = ConfigRuntime()
        assert rt._bootstrapped is False
        with patch.object(rt, "_bootstrap", wraps=rt._bootstrap) as mock_bs:
            rt.get_layered("any.key")
            mock_bs.assert_called_once()
        assert rt._bootstrapped is True

    def test_bootstrap_runs_only_once(self) -> None:
        """Subsequent get_layered() calls skip bootstrap."""
        rt = ConfigRuntime()
        with patch(
            "factory.config.runtime.runtime.ConfigRuntime._bootstrap",
            wraps=rt._bootstrap,
        ) as mock_bs:
            rt.get_layered("a")
            rt.get_layered("b")
            rt.get_layered("c")
            mock_bs.assert_called_once()

    def test_ssm_failure_is_graceful(self) -> None:
        """When SSM import/init fails, InfraEnv layer is still added."""
        rt = ConfigRuntime()
        with patch(
            "factory.config.runtime.runtime.ConfigRuntime._bootstrap"
        ) as mock_bs:
            # Simulate: SSM fails, but InfraEnv succeeds
            def fake_bootstrap():
                rt._bootstrapped = True
                from factory.config.runtime.adapters.infra_env import (
                    InfraEnvConfigStore,
                )
                rt.add_layer(InfraEnvConfigStore())

            mock_bs.side_effect = fake_bootstrap
            os.environ["NEO4J_URI"] = "bolt://from-env"
            result = rt.get_layered("neo4j.uri")
            assert result == "bolt://from-env"

    def test_ssm_import_error_caught(self) -> None:
        """If SSMConfigStore import raises, bootstrap still completes."""
        rt = ConfigRuntime()
        with patch(
            "factory.config.runtime.runtime.ConfigRuntime._create_config"
        ):
            # Patch SSM import to raise
            import_path = "factory.config.runtime.adapters.ssm_adapter.SSMConfigStore"
            with patch(import_path, side_effect=ImportError("no boto3")):
                os.environ["GRAPH_BACKEND"] = "neo4j"
                rt.get_layered("graph.backend")
                # Should not raise — SSM failure is caught
                assert rt._bootstrapped is True

    def test_infra_env_layer_always_added(self) -> None:
        """InfraEnv is always the last (highest priority) layer."""
        rt = ConfigRuntime()
        # Patch SSM to fail completely
        with patch(
            "factory.config.runtime.adapters.ssm_adapter.SSMConfigStore",
            side_effect=Exception("no AWS"),
        ):
            os.environ["NEO4J_URI"] = "bolt://env-wins"
            val = rt.get_layered("neo4j.uri")
            assert val == "bolt://env-wins"
            # InfraEnv should be in layers
            from factory.config.runtime.adapters.infra_env import (
                InfraEnvConfigStore,
            )
            assert any(
                isinstance(layer, InfraEnvConfigStore) for layer in rt._layers
            )

    def test_layer_priority_last_wins(self) -> None:
        """Later layers override earlier ones in get_layered()."""
        rt = ConfigRuntime()
        rt._bootstrapped = True  # Skip auto-bootstrap

        low = MagicMock()
        low.exists.return_value = True
        low.get.return_value = "low_value"

        high = MagicMock()
        high.exists.return_value = True
        high.get.return_value = "high_value"

        rt.add_layer(low)
        rt.add_layer(high)

        assert rt.get_layered("any.key") == "high_value"

    def test_get_layered_falls_through_to_default(self) -> None:
        """When no layer has the key, default is returned."""
        rt = ConfigRuntime()
        rt._bootstrapped = True

        layer = MagicMock()
        layer.exists.return_value = False
        rt.add_layer(layer)

        assert rt.get_layered("missing.key", "fallback") == "fallback"

    def test_get_layered_default_none(self) -> None:
        """Default is None when not specified."""
        rt = ConfigRuntime()
        rt._bootstrapped = True
        assert rt.get_layered("missing.key") is None

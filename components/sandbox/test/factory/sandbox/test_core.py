"""Tests for sandbox core functionality."""

import pytest

from factory.sandbox.core import COMPONENT_NAME, COMPONENT_VERSION, EnvironmentStatus
from factory.sandbox.runtime.adapters.mock import MockAdapter
from factory.sandbox.runtime.models import SandboxConfig
from factory.sandbox.runtime.runtime import SandboxRuntime


class TestSandboxCore:
    """Test core types and constants."""

    def test_component_metadata(self) -> None:
        """Test component metadata is defined."""
        assert COMPONENT_NAME == "sandbox"
        assert COMPONENT_VERSION == "0.1.0"

    def test_environment_status(self) -> None:
        """Test environment status enum."""
        assert EnvironmentStatus.RUNNING == "running"
        assert EnvironmentStatus.TERMINATED == "terminated"


class TestSandboxConfig:
    """Test sandbox configuration model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = SandboxConfig()
        assert config.instance_type == "t3.micro"
        assert config.timeout_seconds == 3600
        assert config.auto_terminate is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = SandboxConfig(instance_type="t3.medium", timeout_seconds=7200)
        assert config.instance_type == "t3.medium"
        assert config.timeout_seconds == 7200


class TestMockAdapter:
    """Test mock sandbox adapter."""

    @pytest.fixture
    def adapter(self) -> MockAdapter:
        """Create mock adapter."""
        return MockAdapter()

    @pytest.mark.asyncio
    async def test_provision_and_terminate(self, adapter: MockAdapter) -> None:
        """Test provisioning and terminating."""
        env_id = await adapter.provision({"instance_type": "t3.micro"})
        assert env_id is not None
        status = await adapter.get_status(env_id)
        assert status["status"] == "running"
        await adapter.terminate(env_id)
        status = await adapter.get_status(env_id)
        assert status["status"] == "terminated"

    @pytest.mark.asyncio
    async def test_execute(self, adapter: MockAdapter) -> None:
        """Test command execution."""
        env_id = await adapter.provision({})
        result = await adapter.execute(env_id, "echo hello")
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    @pytest.mark.asyncio
    async def test_file_operations(self, adapter: MockAdapter) -> None:
        """Test file upload/download."""
        env_id = await adapter.provision({})
        result = await adapter.upload_file(env_id, "/local/file", "/remote/file")
        assert result["success"] is True
        result = await adapter.download_file(env_id, "/remote/file", "/local/file")
        assert result["success"] is True

    def test_health_check(self, adapter: MockAdapter) -> None:
        """Test health check."""
        health = adapter.health_check()
        assert health["healthy"] is True
        assert health["adapter"] == "mock"


class TestSandboxRuntime:
    """Test sandbox runtime."""

    @pytest.fixture
    def runtime(self) -> SandboxRuntime:
        """Create runtime with mock adapter."""
        return SandboxRuntime(MockAdapter())

    @pytest.mark.asyncio
    async def test_provision(self, runtime: SandboxRuntime) -> None:
        """Test provisioning."""
        env = await runtime.provision()
        assert env.env_id is not None
        assert env.instance_type == "t3.micro"

    @pytest.mark.asyncio
    async def test_execute(self, runtime: SandboxRuntime) -> None:
        """Test command execution."""
        env = await runtime.provision()
        result = await runtime.execute(env.env_id, "echo test")
        assert result.success is True
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_list_environments(self, runtime: SandboxRuntime) -> None:
        """Test listing environments includes provisioned ones."""
        env1 = await runtime.provision()
        env2 = await runtime.provision()
        envs = runtime.list_environments()
        env_ids = {e.env_id for e in envs}
        assert env1.env_id in env_ids
        assert env2.env_id in env_ids
        assert len(envs) >= 2

    def test_health_check(self, runtime: SandboxRuntime) -> None:
        """Test runtime health check."""
        health = runtime.health_check()
        assert health["healthy"] is True

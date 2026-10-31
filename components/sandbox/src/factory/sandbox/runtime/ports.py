"""Protocol interfaces for sandbox adapters."""

from typing import Any, Protocol

from .manifest import ProvisionPlan, ProvisionResult, SandboxManifest
from .models import EnvironmentInfo


class SandboxPort(Protocol):
    """Protocol for sandbox environment backends."""

    async def provision(self, config: dict[str, Any]) -> str:
        """Provision a new environment, return environment ID."""
        ...

    async def terminate(self, env_id: str) -> None:
        """Terminate an environment."""
        ...

    async def get_status(self, env_id: str) -> dict[str, Any]:
        """Get environment status."""
        ...

    async def execute(
        self, env_id: str, command: str, timeout_seconds: int = 300
    ) -> dict[str, Any]:
        """Execute command in environment, return output."""
        ...

    async def upload_file(
        self, env_id: str, local_path: str, remote_path: str
    ) -> dict[str, Any]:
        """Upload file to environment."""
        ...

    async def download_file(
        self, env_id: str, remote_path: str, local_path: str
    ) -> dict[str, Any]:
        """Download file from environment."""
        ...

    async def list_files(self, env_id: str, path: str = "/") -> list[dict[str, Any]]:
        """List files in environment directory."""
        ...

    def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        ...


class SandboxStore(Protocol):
    """Port: Sandbox environment persistence."""

    def save(self, env: EnvironmentInfo) -> None: ...
    def load(self, env_id: str) -> EnvironmentInfo | None: ...
    def list_environments(self, status: str | None = None) -> list[EnvironmentInfo]: ...
    def delete(self, env_id: str) -> bool: ...
    def health_check(self) -> dict[str, Any]: ...


class ProvisionerPort(Protocol):
    """Port: translates a SandboxManifest into infrastructure actions."""

    async def plan(self, manifest: SandboxManifest) -> ProvisionPlan: ...
    async def apply(
        self, env_id: str, plan: ProvisionPlan, execute_fn: Any,
    ) -> ProvisionResult: ...

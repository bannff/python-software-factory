"""Mock sandbox adapter for testing."""

import uuid
from typing import Any


class MockAdapter:
    """Mock sandbox adapter for testing without real infrastructure."""

    def __init__(self) -> None:
        """Initialize mock adapter."""
        self._environments: dict[str, dict[str, Any]] = {}
        self._files: dict[str, dict[str, bytes]] = {}

    async def provision(self, config: dict[str, Any]) -> str:
        """Provision mock environment."""
        env_id = str(uuid.uuid4())
        self._environments[env_id] = {
            "config": config,
            "status": "running",
            "public_ip": "10.0.0.1",
            "private_ip": "192.168.1.1",
        }
        self._files[env_id] = {}
        return env_id

    async def terminate(self, env_id: str) -> None:
        """Terminate mock environment."""
        if env_id in self._environments:
            self._environments[env_id]["status"] = "terminated"

    async def get_status(self, env_id: str) -> dict[str, Any]:
        """Get mock environment status."""
        if env_id not in self._environments:
            return {"status": "unknown"}
        env = self._environments[env_id]
        return {
            "status": env["status"],
            "public_ip": env.get("public_ip"),
            "private_ip": env.get("private_ip"),
        }

    async def execute(
        self, env_id: str, command: str, timeout_seconds: int = 300
    ) -> dict[str, Any]:
        """Execute mock command."""
        if env_id not in self._environments:
            return {"exit_code": 1, "stderr": "Environment not found", "stdout": "", "duration_ms": 0}
        return {
            "exit_code": 0,
            "stdout": f"Mock output for: {command}",
            "stderr": "",
            "duration_ms": 100,
        }

    async def upload_file(
        self, env_id: str, local_path: str, remote_path: str
    ) -> dict[str, Any]:
        """Upload mock file."""
        if env_id not in self._environments:
            return {"success": False, "error": "Environment not found"}
        self._files[env_id][remote_path] = b"mock content"
        return {"success": True, "remote_path": remote_path}

    async def download_file(
        self, env_id: str, remote_path: str, local_path: str
    ) -> dict[str, Any]:
        """Download mock file."""
        if env_id not in self._environments:
            return {"success": False, "error": "Environment not found"}
        return {"success": True, "local_path": local_path, "size_bytes": 12}

    async def list_files(self, env_id: str, path: str = "/") -> list[dict[str, Any]]:
        """List mock files."""
        if env_id not in self._environments:
            return []
        return [
            {"name": "file.txt", "path": f"{path}/file.txt", "size_bytes": 100, "is_directory": False},
            {"name": "dir", "path": f"{path}/dir", "size_bytes": 0, "is_directory": True},
        ]

    def health_check(self) -> dict[str, Any]:
        """Check mock adapter health."""
        return {"healthy": True, "adapter": "mock", "environments": len(self._environments)}

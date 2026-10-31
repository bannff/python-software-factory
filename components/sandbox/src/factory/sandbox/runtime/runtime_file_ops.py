"""Sandbox runtime file operations (secret-aware)."""
from __future__ import annotations

from typing import Any

from .event_emitter import emit
from .event_payloads import base_env_payload
from .models import EnvironmentInfo


class RuntimeFileOpsMixin:
    """Secret-aware inline file operations for SandboxRuntime."""

    def _file_access_denied(self, env_id: str, env: EnvironmentInfo | None) -> bool:
        """Fail closed if secret state is enabled or Docker cannot verify it."""
        if env and env.metadata.get("secret_mounts_enabled", False):
            return True
        from .adapters.docker_adapter import DockerAdapter

        return isinstance(self._adapter, DockerAdapter) and (
            self._adapter.get_secret_output_suppression(env_id) is not False
        )


    async def write_file(
        self, env_id: str, remote_path: str, content: str, encoding: str = "utf8",
    ) -> dict[str, Any]:
        """Write inline content to a file inside the environment.

        Decodes content (utf8|base64), stages it, and copies it in — no caller
        host staging or shell escaping. Malformed input surfaces as a failure
        result rather than a transport error.
        """
        env = self._store.load(env_id)
        if self._file_access_denied(env_id, env):
            result = {
                "success": False,
                "error": "File operations are disabled for secret-enabled or unverified sandboxes",
            }
        else:
            from .file_ops import write_file as _write
            try:
                result = await _write(
                    self._adapter.upload_file, env_id, remote_path, content, encoding,
                )
            except (ValueError, OSError) as exc:
                result = {"success": False, "error": str(exc)}
        emit("sandbox.file_written", base_env_payload(env_id, env) | {
            "remote_path": remote_path,
            "encoding": encoding,
            "bytes_written": result.get("bytes_written"),
            "success": bool(result.get("success", False)),
        })
        return result


    async def diff(self, env_id: str, path: str = ".") -> dict[str, Any]:
        """Report changed files (tracked + untracked) under ``path`` via git."""
        env = self._store.load(env_id)
        if self._file_access_denied(env_id, env):
            result = {"is_git_repo": False, "path": path, "files": [], "stat": ""}
        else:
            from .diff_ops import git_diff
            result = await git_diff(self._adapter.execute, env_id, path)
        emit("sandbox.files_changed", base_env_payload(env_id, env) | {
            "path": path,
            "is_git_repo": bool(result.get("is_git_repo", False)),
            "changed_count": len(result.get("files", [])),
        })
        return result


    async def upload_file(
        self, env_id: str, local_path: str, remote_path: str
    ) -> dict[str, Any]:
        """Upload file to environment."""
        env = self._store.load(env_id)
        if self._file_access_denied(env_id, env):
            result = {
                "success": False,
                "error": "File operations are disabled for secret-enabled or unverified sandboxes",
            }
        else:
            result = await self._adapter.upload_file(env_id, local_path, remote_path)
        emit("sandbox.file_uploaded", base_env_payload(env_id, env) | {
            "local_path": local_path,
            "remote_path": remote_path,
            "success": bool(result.get("success", False)),
        })
        return result


    async def download_file(
        self, env_id: str, remote_path: str, local_path: str
    ) -> dict[str, Any]:
        """Download file from environment."""
        env = self._store.load(env_id)
        if self._file_access_denied(env_id, env):
            result = {
                "success": False,
                "error": "Downloads are disabled for secret-enabled or unverified sandboxes",
            }
        else:
            result = await self._adapter.download_file(
                env_id, remote_path, local_path,
            )
        emit("sandbox.file_downloaded", base_env_payload(env_id, env) | {
            "remote_path": remote_path,
            "local_path": local_path,
            "success": bool(result.get("success", False)),
            "size_bytes": result.get("size_bytes"),
        })
        return result



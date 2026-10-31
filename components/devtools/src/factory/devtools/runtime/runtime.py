"""Devtools runtime composition for bounded project reads."""
from __future__ import annotations

from .file_ops import list_dir, read_file
from .models import ProjectBinding
from .search_ops import search


class DevtoolsRuntime:
    def read_file(
        self, binding: ProjectBinding, path: str,
        offset: int = 0, limit: int = 2000,
    ):
        return read_file(binding, path, offset, limit)

    def create_file(self, binding: ProjectBinding, path: str, content: str):
        from .file_write_ops import create_file
        return create_file(binding, path, content)

    def edit_file(
        self, binding: ProjectBinding, path: str,
        content: str, base_sha256: str,
    ):
        from .file_write_ops import edit_file
        return edit_file(binding, path, content, base_sha256)

    def list_dir(
        self, binding: ProjectBinding, path: str = ".", limit: int = 500,
    ):
        return list_dir(binding, path, limit)

    def search(
        self, binding: ProjectBinding, query: str,
        path: str = ".", glob: str | None = None, limit: int = 100,
    ):
        return search(binding, query, path, glob, limit)

    def run_command(
        self, binding: ProjectBinding, argv: list[str], cwd: str = ".", *,
        timeout_seconds: float = 60.0, output_limit: int = 65_536,
        cancel_event=None, correlation_id: str | None = None,
    ):
        from .command_runner import run_command
        return run_command(
            binding, argv, cwd, timeout_seconds=timeout_seconds,
            output_limit=output_limit, cancel_event=cancel_event,
            correlation_id=correlation_id,
        )

    def cancel_command(self, binding: ProjectBinding, run_id: str) -> bool:
        from .command_cancel import cancel
        return cancel(binding, run_id)

    def git_status(self, binding: ProjectBinding):
        from .git_ops import git_status
        return git_status(binding)

    def git_diff(self, binding: ProjectBinding, paths: list[str], *, staged: bool = False):
        from .git_ops import git_diff
        return git_diff(binding, paths, staged=staged)

    def git_log(self, binding: ProjectBinding, paths: list[str] | None = None, *, limit: int = 20):
        from .git_ops import git_log
        return git_log(binding, paths, limit=limit)

    def git_stage(self, binding: ProjectBinding, paths: list[str]):
        from .git_ops import git_stage
        return git_stage(binding, paths)

    def git_commit(self, binding: ProjectBinding, message: str, *, skip_hooks: bool = False):
        from .git_ops import git_commit
        return git_commit(binding, message, skip_hooks=skip_hooks)

    def git_push(
        self, binding: ProjectBinding, remote: str, branch: str, *,
        set_upstream: bool = False,
    ):
        from .git_ops import git_push
        return git_push(binding, remote, branch, set_upstream=set_upstream)

    @staticmethod
    def health_check() -> dict[str, object]:
        return {"healthy": True, "backend": "local"}


_runtime: DevtoolsRuntime | None = None


def get_runtime() -> DevtoolsRuntime:
    global _runtime
    if _runtime is None:
        _runtime = DevtoolsRuntime()
    return _runtime


__all__ = ["DevtoolsRuntime", "get_runtime"]

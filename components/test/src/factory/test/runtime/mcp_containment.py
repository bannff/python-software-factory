"""MCP-only path validation and contained Test-runtime execution."""
from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath
from typing import Any

from .mcp_projection import (
    discovery as project_discovery,
    execution as project_execution,
    junit as project_junit,
    rejected_discovery,
    rejected_execution,
    rejected_junit,
    relative,
)
from .ports import TestDiscoveryResult, TestResult
from .runtime import TestRuntime

_COMPONENT = r"^[a-z][a-z0-9_-]{0,63}$"


def is_valid_pattern(pattern: object) -> bool:
    """Accept only a non-empty, workspace-relative POSIX glob pattern."""
    if not isinstance(pattern, str) or not pattern or not pattern.strip():
        return False
    if "\x00" in pattern or "\\" in pattern or pattern.startswith(("/", "~")):
        return False
    windows = PureWindowsPath(pattern)
    if windows.is_absolute() or windows.drive:
        return False
    return all(part not in {"", ".", ".."} for part in pattern.split("/"))


class ContainmentError(ValueError):
    """Raised before an MCP tool reads a path or spawns a subprocess."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class McpTestRuntime:
    """Safe MCP facade; direct ``TestRuntime`` remains trusted-local for CI."""

    def __init__(self, runtime: TestRuntime) -> None:
        self._runtime = runtime
        root = getattr(runtime, "root_dir", None)
        if not isinstance(root, (str, Path)):
            raise ContainmentError("runtime_root_unavailable")
        self._root = Path(root).resolve(strict=False)
        if not self._root.is_absolute():
            raise ContainmentError("runtime_root_unavailable")

    def discover(self, path: str, pattern: str, *, pattern_supplied: bool = True) -> dict[str, Any]:
        pattern = self._pattern(self._effective_pattern(pattern, pattern_supplied))
        target = self._target(path)
        exists = self._stable_exists(target)
        result = (TestDiscoveryResult(errors=["target_not_found"]) if not exists
                  else self._runtime.discover_tests(self._relative(target), pattern))
        return project_discovery(self._root, target, result)

    def run_all(self, verbose: bool, *, verbose_supplied: bool = True) -> dict[str, Any]:
        return self._run(self._root, self._effective_verbose(verbose, verbose_supplied),
                         self._pattern(self._default_pattern()))

    def run_component(self, component: str, verbose: bool, *, verbose_supplied: bool = True) -> dict[str, Any]:
        if not isinstance(component, str) or not re.fullmatch(_COMPONENT, component):
            raise ContainmentError("invalid_component")
        target = self._target(f"components/{component}/test")
        return self._run(target, self._effective_verbose(verbose, verbose_supplied),
                         self._pattern(self._default_pattern()), component=component)

    def run_path(self, path: str, pattern: str, verbose: bool, *,
                 pattern_supplied: bool = True, verbose_supplied: bool = True) -> dict[str, Any]:
        pattern = self._pattern(self._effective_pattern(pattern, pattern_supplied))
        target = self._target(path)
        return self._run(target, self._effective_verbose(verbose, verbose_supplied), pattern,
                         path=self._relative(target))

    def compare_junit(self, base: str, candidate: str) -> dict[str, Any]:
        self._path_parts(base)
        self._path_parts(candidate)
        base_target, candidate_target = self._target(base), self._target(candidate)
        base_exists, candidate_exists = self._stable_exists(base_target), self._stable_exists(candidate_target)
        if not base_exists or not candidate_exists:
            result = {"passed": False, "errors": ["target_not_found"]}
        elif not base_target.is_file() or not candidate_target.is_file():
            result = {"passed": False, "errors": ["invalid_report"]}
        else:
            self._assert_stable(base_target)
            self._assert_stable(candidate_target)
            result = self._runtime.compare_junit(
                base_target, candidate_target, nofollow=True
            )
        return project_junit(self._root, base_target, candidate_target, result)

    def list_files(self) -> dict[str, Any]:
        found = self.discover(".", self._default_pattern())
        return {"test_files": found["test_files"], "count": len(found["test_files"]),
                "errors": found["errors"], "diagnostics": found["diagnostics"],
                "test_files_truncated": found["test_files_truncated"],
                "diagnostics_truncated": found["diagnostics_truncated"]}

    def rejected_discovery(self, code: str) -> dict[str, Any]:
        return rejected_discovery(code)

    def rejected_execution(self, code: str) -> dict[str, Any]:
        return rejected_execution(code)

    def rejected_junit(self, code: str) -> dict[str, Any]:
        return rejected_junit(code)

    def _path_parts(self, supplied: str) -> tuple[str, ...]:
        if not isinstance(supplied, str) or not supplied or not supplied.strip() or "\x00" in supplied:
            raise ContainmentError("invalid_path")
        if supplied == ".":
            return ()
        windows = PureWindowsPath(supplied)
        if supplied.startswith(("/", "\\", "~")) or windows.is_absolute() or windows.drive:
            raise ContainmentError("invalid_path")
        if "\\" in supplied or ":" in supplied.split("/", 1)[0]:
            raise ContainmentError("invalid_path")
        parts = tuple(supplied.split("/"))
        if any(part in {"", ".", ".."} for part in parts):
            raise ContainmentError("invalid_path")
        return parts

    def _target(self, supplied: str) -> Path:
        parts = self._path_parts(supplied)
        if not parts:
            return self._root
        candidate, current = self._root.joinpath(*parts), self._root
        for part in parts:
            current /= part
            if current.is_symlink():
                raise ContainmentError("unsafe_path")
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(self._root):
            raise ContainmentError("unsafe_path")
        return resolved

    def _assert_stable(self, target: Path) -> None:
        """Recheck every component immediately before a filesystem operation."""
        try:
            parts = target.relative_to(self._root).parts
        except ValueError as exc:
            raise ContainmentError("unsafe_path") from exc
        current = self._root
        for part in parts:
            current /= part
            if current.is_symlink():
                raise ContainmentError("unsafe_path")
        if target.exists() and target.resolve(strict=True) != target:
            raise ContainmentError("unsafe_path")

    def _stable_exists(self, target: Path) -> bool:
        self._assert_stable(target)
        return target.exists()

    def _pattern(self, pattern: str) -> str:
        if not is_valid_pattern(pattern):
            raise ContainmentError("invalid_pattern")
        return pattern

    def _run(self, target: Path, verbose: bool, pattern: str, *, component: str | None = None,
             path: str | None = None) -> dict[str, Any]:
        exists = self._stable_exists(target)
        result = (TestResult(errors=["target_not_found"]) if not exists else
                  self._runtime.run_tests(self._relative(target), pattern, verbose))
        return project_execution(self._root, target, result, component=component, path=path)

    def _relative(self, target: Path) -> str:
        return relative(self._root, target)

    def _default_pattern(self) -> str:
        return str(getattr(self._runtime, "default_pattern", "test_*.py"))

    def _effective_pattern(self, requested: str, supplied: bool = True) -> str:
        return requested if supplied else self._default_pattern()

    def _effective_verbose(self, requested: bool, supplied: bool = True) -> bool:
        return bool(requested) if supplied else bool(getattr(self._runtime, "default_verbose", False))

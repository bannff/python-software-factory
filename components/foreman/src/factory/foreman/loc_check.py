"""Strict and pull-request-ratcheted Python file-size checks."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

_SHA_RE = re.compile(r"[0-9a-fA-F]{7,64}")


def _python_file(path: str) -> bool:
    return path.endswith(".py") and Path(path).name != "__init__.py"


def _count_head(root: Path, path: str) -> int:
    return len((root / path).read_text().splitlines())


def _git(root: Path, args: list[str], *, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], capture_output=True, text=text, check=False, cwd=root
    )


def _base_lines(root: Path, base_sha: str, path: str) -> int:
    result = _git(root, ["show", f"{base_sha}:{path}"])
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or f"cannot read base file: {path}")
    return len(result.stdout.splitlines())


def _diff_entries(root: Path, base_sha: str) -> list[tuple[str, str, str | None]]:
    result = _git(
        root,
        ["diff", "--name-status", "-z", "-M", base_sha, "HEAD", "--", "components", "bases"],
        text=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.decode(errors="replace").strip() or "git diff failed")
    tokens = result.stdout.split(b"\0")
    entries: list[tuple[str, str, str | None]] = []
    index = 0
    while index < len(tokens) and tokens[index]:
        status = tokens[index].decode("ascii", errors="replace")
        index += 1
        old_path = tokens[index].decode(errors="surrogateescape")
        index += 1
        if status.startswith(("R", "C")):
            new_path = tokens[index].decode(errors="surrogateescape")
            index += 1
            entries.append((status, new_path, old_path))
        else:
            entries.append((status, old_path, None))
    return entries


def _strict(root: Path, max_lines: int) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    checked = 0
    for area in ("components", "bases"):
        search_path = root / area
        if not search_path.exists():
            continue
        for py_file in search_path.rglob("*.py"):
            if "__pycache__" in py_file.parts or py_file.name == "__init__.py":
                continue
            try:
                line_count = len(py_file.read_text().splitlines())
            except Exception:
                continue
            checked += 1
            if line_count > max_lines:
                violations.append(
                    {"file": str(py_file.relative_to(root)), "lines": line_count,
                     "over_by": line_count - max_lines}
                )
    return _result("strict", max_lines, checked, violations)


def _result(
    mode: str, max_lines: int, checked: int, violations: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "check": "file_sizes", "mode": mode, "passed": not violations,
        "max_lines": max_lines, "files_checked": checked,
        "violations": violations[:20], "total_violations": len(violations),
    }


def _failure(mode: str, max_lines: int, error: str) -> dict[str, Any]:
    return {**_result(mode, max_lines, 0, []), "passed": False, "error": error}


def _ratchet(root: Path, max_lines: int, base_sha: str | None) -> dict[str, Any]:
    if not base_sha:
        return _failure("ratchet", max_lines, "base_sha is required for ratchet mode")
    if not _SHA_RE.fullmatch(base_sha):
        return _failure("ratchet", max_lines, "base_sha must be a hexadecimal commit SHA")
    verify = _git(root, ["rev-parse", "--verify", "--quiet", f"{base_sha}^{{commit}}"])
    if verify.returncode != 0:
        return _failure("ratchet", max_lines, f"base_sha does not resolve: {base_sha}")

    violations: list[dict[str, Any]] = []
    checked = 0
    try:
        for status, head_path, old_path in _diff_entries(root, base_sha):
            if status.startswith("D") or not _python_file(head_path):
                continue
            checked += 1
            head_lines = _count_head(root, head_path)
            base_lines = None if status.startswith("A") else _base_lines(
                root, base_sha, old_path or head_path
            )
            reason = None
            if base_lines is None and head_lines > max_lines:
                reason = "new_file_over_limit"
            elif base_lines is not None and base_lines <= max_lines < head_lines:
                reason = "newly_over_limit"
            elif base_lines is not None and base_lines > max_lines and head_lines > base_lines:
                reason = "legacy_file_grew"
            if reason:
                violations.append(
                    {"file": head_path, "lines": head_lines, "base_lines": base_lines,
                     "over_by": head_lines - max_lines, "reason": reason}
                )
    except (OSError, UnicodeError, ValueError) as exc:
        return _failure("ratchet", max_lines, str(exc))
    return _result("ratchet", max_lines, checked, violations)


def check_file_sizes(
    workspace_root: Path | None = None,
    max_lines: int = 200,
    mode: str = "strict",
    base_sha: str | None = None,
) -> dict[str, Any]:
    """Check whole-tree LOC by default, or compare HEAD against a PR base."""
    root = workspace_root or Path.cwd()
    if mode == "strict":
        return _strict(root, max_lines)
    if mode == "ratchet":
        return _ratchet(root, max_lines, base_sha)
    return _failure(mode, max_lines, f"unknown file-size mode: {mode}")

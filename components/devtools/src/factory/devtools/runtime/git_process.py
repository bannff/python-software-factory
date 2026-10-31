"""Bounded helper-disabled git process execution."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

from .command_policy import minimal_environment
from .models import ProjectBinding
from .output_safety import sanitize_output

_FCHDIR_EXEC = "import os,sys;os.fchdir(int(sys.argv[1]));os.execv(sys.argv[2],sys.argv[2:])"


class GitRefused(ValueError):
    pass


class GitFailed(RuntimeError):
    pass


def run_git(
    binding: ProjectBinding, args: list[str], *, timeout: float = 15,
    limit: int = 131_072, allowed: set[int] | None = None,
) -> tuple[str, bool, int]:
    root = Path(binding.root).resolve(strict=True)
    git = shutil.which("git", path=os.environ.get("PATH", ""))
    if not git or _inside(Path(git).resolve(strict=True), root):
        raise GitRefused("trusted git executable is unavailable")
    prefix = [
        git, "-c", "core.pager=cat", "-c", "pager.status=false",
        "-c", "pager.diff=false", "-c", "pager.log=false",
        "-c", "credential.helper=", "-c", "core.fsmonitor=false",
    ]
    directory_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        process = subprocess.Popen(
            [sys.executable, "-c", _FCHDIR_EXEC, str(directory_fd), *prefix, *args],
            shell=False, pass_fds=(directory_fd,), env=_git_env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )
    finally:
        os.close(directory_fd)
    boxes = [bytearray(), bytearray()]
    truncated = [False, False]
    threads = [
        threading.Thread(target=_drain, args=(pipe, boxes[i], truncated, i, limit), daemon=True)
        for i, pipe in enumerate((process.stdout, process.stderr))
    ]
    for thread in threads:
        thread.start()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill(process)
        raise GitFailed("git operation timed out") from exc
    for thread in threads:
        thread.join(timeout=2)
    stdout = sanitize_output(boxes[0].decode("utf-8", "replace"))
    stderr = sanitize_output(boxes[1].decode("utf-8", "replace"))
    if process.returncode not in (allowed or {0}):
        raise GitFailed(stderr or "git operation failed")
    return stdout if stdout else stderr, any(truncated), process.returncode


def _drain(pipe, box: bytearray, truncated: list[bool], index: int, limit: int) -> None:
    while chunk := pipe.read(4096):
        remaining = limit - len(box)
        box.extend(chunk[:max(0, remaining)])
        truncated[index] |= len(chunk) > remaining
    pipe.close()


def _git_env() -> dict[str, str]:
    env = minimal_environment()
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat",
        "GIT_EXTERNAL_DIFF": "", "GIT_OPTIONAL_LOCKS": "0",
    })
    return env


def _kill(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


__all__ = ["GitFailed", "GitRefused", "run_git"]

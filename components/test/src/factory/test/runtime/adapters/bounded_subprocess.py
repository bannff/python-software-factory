"""Bounded subprocess capture and process-group cleanup for test adapters."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessCapture:
    """Small, bounded result from one child-process invocation."""

    returncode: int
    output: str
    timed_out: bool = False
    truncated: bool = False
    error: str | None = None


def run_bounded(
    command: list[str],
    *,
    cwd: Path,
    timeout: float,
    max_output: int = 64 * 1024,
) -> ProcessCapture:
    """Run argv without a shell, draining output while enforcing limits."""
    popen_options: dict[str, object] = {
        "cwd": str(cwd), "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
        "start_new_session": os.name == "posix",
    }
    if os.name == "nt":
        popen_options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        process = subprocess.Popen(command, **popen_options)
    except OSError as exc:
        return ProcessCapture(-1, "", error=str(exc))

    assert process.stdout is not None
    selector = selectors.DefaultSelector()
    chunks: list[bytes] = []
    captured = 0
    timed_out = False
    truncated = False
    started = time.monotonic()

    def kill_group() -> None:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            elif process.poll() is None:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                except OSError:
                    process.kill()
        except (OSError, ProcessLookupError):
            pass

    try:
        selector.register(process.stdout, selectors.EVENT_READ)
        while selector.get_map():
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                timed_out = True
                kill_group()
                break
            for key, _ in selector.select(min(remaining, 0.1)):
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                if captured < max_output:
                    kept = chunk[: max_output - captured]
                    chunks.append(kept)
                    captured += len(kept)
                    truncated = truncated or len(kept) < len(chunk)
                else:
                    truncated = True
        if timed_out:
            kill_group()
        try:
            returncode = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            kill_group()
            returncode = process.wait(timeout=1)
    finally:
        selector.close()
        if process.poll() is None:
            kill_group()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)
        process.stdout.close()

    output = b"".join(chunks).decode("utf-8", errors="replace")
    if timed_out:
        return ProcessCapture(returncode, output, timed_out=True, truncated=truncated)
    return ProcessCapture(returncode, output, truncated=truncated)

"""Bounded project command execution with process-group teardown."""
from __future__ import annotations

import codecs
import hashlib
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from . import command_cancel
from factory.mcp_utils.interface import event_bus

from .command_policy import minimal_environment, resolve_command
from .models import CommandResult, ProjectBinding
from .output_safety import OutputRefused, sanitize_output
from .path_resolver import resolve_path

_MAX_PROCESSES = 4
_FCHDIR_EXEC = (
    "import os,sys; os.fchdir(int(sys.argv[1])); "
    "os.execv(sys.argv[2], sys.argv[2:])"
)
_SLOTS = threading.BoundedSemaphore(_MAX_PROCESSES)


class CommandBusy(RuntimeError):
    pass


class _Capture:
    def __init__(self, stream: str, limit: int, publish) -> None:
        self.stream, self.limit, self.publish = stream, limit, publish
        self.parts: list[str] = []
        self.length = 0
        self.pending = ""
        self.truncated = False
        self.unsafe: OutputRefused | None = None
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def read(self, pipe) -> None:
        try:
            while chunk := pipe.read(4096):
                self._feed(self.decoder.decode(chunk), final=False)
            self._feed(self.decoder.decode(b"", final=True), final=True)
        except OutputRefused as exc:
            self.unsafe = exc
        finally:
            pipe.close()

    def _feed(self, value: str, *, final: bool) -> None:
        clean = sanitize_output(self.pending + value)
        if final:
            self.pending = ""
            self._append(clean)
        elif len(clean) <= 256:
            self.pending = clean
        else:
            self.pending = clean[-256:]
            self._append(clean[:-256])

    def _append(self, value: str) -> None:
        if not value:
            return
        remaining = self.limit - self.length
        emitted = value[:max(0, remaining)]
        if emitted:
            self.parts.append(emitted)
            self.length += len(emitted)
            self.publish(self.stream, emitted)
        if len(value) > len(emitted):
            self.truncated = True

    @property
    def text(self) -> str:
        return "".join(self.parts)


def run_command(
    binding: ProjectBinding, argv: list[str], cwd: str = ".", *,
    timeout_seconds: float = 60.0, output_limit: int = 65_536,
    cancel_event: threading.Event | None = None,
    correlation_id: str | None = None,
) -> CommandResult:
    if not 1.0 <= timeout_seconds <= 120.0:
        raise ValueError("command timeout is outside bounds")
    if not 1024 <= output_limit <= 131_072:
        raise ValueError("command output limit is outside bounds")
    if not _SLOTS.acquire(blocking=False):
        raise CommandBusy("command concurrency limit reached")
    started = time.monotonic()
    run_id = f"cmd_{uuid4().hex}"
    effective_cancel = cancel_event or threading.Event()
    command_cancel.register(run_id, binding, effective_cancel)
    try:
        root = Path(binding.root).resolve(strict=True)
        workdir = resolve_path(binding, cwd, expect="dir")
        executable, normalized = resolve_command(root, argv)
        argument_digest = hashlib.sha256("\0".join(normalized[1:]).encode()).hexdigest()
        sequence = 0
        sequence_lock = threading.Lock()

        def publish(event: str, **values) -> None:
            nonlocal sequence
            with sequence_lock:
                sequence += 1
                current = sequence
            payload = {"run_id": run_id, "sequence": current, **values}
            event_bus.publish({
                "event_type": event, "source": "devtools",
                "correlation_id": correlation_id,
                "payload": {**payload, "correlation_id": correlation_id},
            })

        def publish_output(stream: str, text: str) -> None:
            publish("devtools.command.output", stream=stream, text=text)

        relative_cwd = str(workdir.relative_to(root)) or "."
        publish(
            "devtools.command.started", executable=Path(executable).name,
            argument_digest=argument_digest, cwd=relative_cwd,
        )
        directory_fd = os.open(
            workdir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) |
            getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            process = subprocess.Popen(
                [sys.executable, "-c", _FCHDIR_EXEC, str(directory_fd),
                 executable, *normalized[1:]],
                shell=False, pass_fds=(directory_fd,),
                env=minimal_environment(), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=True,
            )
        finally:
            os.close(directory_fd)
        stdout = _Capture("stdout", output_limit, publish_output)
        stderr = _Capture("stderr", output_limit, publish_output)
        threads = [
            threading.Thread(target=stdout.read, args=(process.stdout,), daemon=True),
            threading.Thread(target=stderr.read, args=(process.stderr,), daemon=True),
        ]
        for thread in threads:
            thread.start()
        timed_out = cancelled = False
        deadline = started + timeout_seconds
        while process.poll() is None:
            if effective_cancel.is_set():
                cancelled = True
                _terminate_group(process)
                break
            if time.monotonic() >= deadline:
                timed_out = True
                _terminate_group(process)
                break
            time.sleep(0.02)
        process.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=2)
        unsafe = stdout.unsafe or stderr.unsafe
        duration = int((time.monotonic() - started) * 1000)
        truncated = stdout.truncated or stderr.truncated
        digest = hashlib.sha256(
            (stdout.text + "\0" + stderr.text).encode(),
        ).hexdigest()
        publish(
            "devtools.command.finished", exit_code=process.returncode,
            duration_ms=duration, timed_out=timed_out, cancelled=cancelled,
            truncated=truncated, output_digest=digest, success=unsafe is None,
        )
        if unsafe is not None:
            raise unsafe
        return CommandResult(
            run_id=run_id, argv=normalized, cwd=relative_cwd,
            stdout=stdout.text, stderr=stderr.text, exit_code=process.returncode,
            duration_ms=duration, timed_out=timed_out, cancelled=cancelled,
            truncated=truncated, output_sha256=digest,
        )
    finally:
        command_cancel.unregister(run_id)
        _SLOTS.release()


def _terminate_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


__all__ = ["CommandBusy", "run_command"]

"""Hardened fresh-interpreter adapter for closed native LightGBM operations."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from ..native_lightgbm_contracts import (
    REQUEST_ADAPTER, RESPONSE_ADAPTER, NativeFailure, NativeRequest, NativeResult,
)
from .native_process_io import drain_pipe, write_pipe

_MAX_INPUT = 65_536
_MAX_STDOUT = 32 * 1024 * 1024
_MAX_STDERR = 4_096
_WORKER_PATH = Path(__file__).parents[1] / "native_lightgbm_worker.py"
_EXPECTED_KIND = {
    "fit_predict_persist": "fit", "inspect_mlflow": "inspect",
    "inspect_joblib": "inspect", "score_mlflow": "score", "score_joblib": "score",
}


class NativeProcessError(ValueError):
    """Stable public failure classification for native subprocess isolation."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        suffix = f": {detail}" if detail else ""
        super().__init__(f"{code}{suffix}")


class SubprocessNativeLightGBM:
    """Launch one new interpreter per native operation; never retries."""

    def __init__(self, timeout_seconds: float = 60.0) -> None:
        if not 0.05 <= timeout_seconds <= 3_600.0:
            raise ValueError("native process timeout is outside the supported range")
        self._timeout = float(timeout_seconds)

    def execute(self, request: NativeRequest) -> NativeResult:
        raw = REQUEST_ADAPTER.dump_json(request)
        if len(raw) > _MAX_INPUT:
            raise NativeProcessError("native_process_protocol_error", "input too large")
        with tempfile.TemporaryDirectory(prefix="ml-native-lightgbm-") as work:
            private = Path(work)
            os.chmod(private, 0o700)
            try:
                process = subprocess.Popen(
                    self._command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, cwd=Path(sys.executable).absolute().parent,
                    env=self._environment(private), close_fds=True,
                    start_new_session=True,
                )
            except OSError as exc:
                raise NativeProcessError(
                    "native_process_crash", _sanitize_text(str(exc)),
                ) from exc
            stdout, stdout_over = drain_pipe(process.stdout, _MAX_STDOUT)
            stderr, _ = drain_pipe(process.stderr, _MAX_STDERR)
            writer = write_pipe(process.stdin, raw)
            try:
                process.wait(timeout=self._timeout)
            except subprocess.TimeoutExpired as exc:
                _kill_and_wait(process)
                raise NativeProcessError("native_process_timeout") from exc
            finally:
                writer.join()
                stdout_done, stderr_done = stdout.join(), stderr.join()
            if not stdout_done or not stderr_done:
                _kill_group(process.pid)
                raise NativeProcessError(
                    "native_process_protocol_error", "subprocess pipes remained open",
                )
            if writer.error is not None and process.returncode == 0:
                raise NativeProcessError(
                    "native_process_crash", _sanitize_text(str(writer.error)),
                )
            err = _sanitize(stderr.data)
            if process.returncode != 0:
                raise NativeProcessError(
                    "native_process_crash", _exit_detail(process.returncode, err),
                )
            if stdout_over.value:
                raise NativeProcessError("native_process_protocol_error", "output too large")
            try:
                response = RESPONSE_ADAPTER.validate_json(bytes(stdout.data), strict=True)
            except Exception as exc:
                raise NativeProcessError("native_process_protocol_error", err) from exc
            if response.operation != request.operation:
                raise NativeProcessError("native_process_protocol_error", "operation mismatch")
            if isinstance(response, NativeFailure):
                raise NativeProcessError("native_operation_failed", response.error)
            if response.result.kind != _EXPECTED_KIND[request.operation]:
                raise NativeProcessError("native_process_protocol_error", "result mismatch")
            return response.result

    @staticmethod
    def _command() -> list[str]:
        return [sys.executable, str(_WORKER_PATH)]

    @staticmethod
    def _environment(tempdir: Path) -> dict[str, str]:
        environment = {
            "TMPDIR": str(tempdir), "LANG": "C", "LC_ALL": "C",
            "PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
            "LOKY_MAX_CPU_COUNT": "1",
        }
        if os.name == "nt" and "SYSTEMROOT" in os.environ:
            environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        return environment


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (AttributeError, ProcessLookupError, PermissionError):
        pass


def _kill_and_wait(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (AttributeError, ProcessLookupError, PermissionError):
        process.kill()
    process.wait()


def _exit_detail(returncode: int, stderr: str) -> str:
    status = f"signal={-returncode}" if returncode < 0 else f"exit={returncode}"
    return f"{status} {stderr}".strip()


def _sanitize(raw: bytearray) -> str:
    return _sanitize_text(bytes(raw).decode("utf-8", "replace")[:_MAX_STDERR])


def _sanitize_text(text: str) -> str:
    return "".join(
        char if 32 <= ord(char) < 127 else " " for char in text[:_MAX_STDERR]
    ).strip()


__all__ = ["NativeProcessError", "SubprocessNativeLightGBM"]

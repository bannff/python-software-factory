"""Bounded pipe helpers for one-shot native subprocess adapters."""
from __future__ import annotations

import threading


class OverflowFlag:
    value = False


class PipeWriter:
    def __init__(self, thread: threading.Thread) -> None:
        self._thread = thread
        self.error: OSError | None = None

    def join(self) -> None:
        self._thread.join(timeout=5.0)


class PipeDrain:
    def __init__(self, thread: threading.Thread, data: bytearray) -> None:
        self._thread, self.data = thread, data

    def join(self) -> bool:
        self._thread.join(timeout=5.0)
        return not self._thread.is_alive()


def write_pipe(stream, raw: bytes) -> PipeWriter:
    """Write bounded request bytes without blocking the timeout controller."""
    writer: PipeWriter

    def write() -> None:
        if stream is None:
            return
        try:
            stream.write(raw)
            stream.close()
        except BrokenPipeError:
            pass
        except OSError as exc:
            writer.error = exc

    thread = threading.Thread(target=write, daemon=True)
    writer = PipeWriter(thread)
    thread.start()
    return writer


def drain_pipe(stream, limit: int) -> tuple[PipeDrain, OverflowFlag]:
    """Drain a child pipe completely while retaining at most ``limit`` bytes."""
    data, overflow = bytearray(), OverflowFlag()

    def read() -> None:
        if stream is None:
            return
        for chunk in iter(lambda: stream.read(65_536), b""):
            remaining = limit - len(data)
            if remaining > 0:
                data.extend(chunk[:remaining])
            if len(chunk) > max(remaining, 0):
                overflow.value = True

    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    return PipeDrain(thread, data), overflow


__all__ = ["PipeDrain", "PipeWriter", "drain_pipe", "write_pipe"]

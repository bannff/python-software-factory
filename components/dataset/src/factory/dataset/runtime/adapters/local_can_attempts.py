"""Durable local create-or-match store for CAN workflow attempts."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Iterator

from ..atomic_io import (
    atomic_write, atomic_write_immutable, open_file_no_follow,
    read_bytes_no_follow,
)
from ..can_terminal_canonical import canonical_json
from ..can_terminal_models import CanAttemptRecord, make_attempt_record
from ..can_terminal_paths import checked_output_path


class LocalCanAttemptStore:
    """Serialize one explicit attempt and publish a terminal pointer last."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.base = self.root / "can_terminal"
        self.attempts = self.base / "attempts"
        self.terminals = self.base / "terminals"
        self.locks = self.base / "locks"
        for path in (self.base, self.attempts, self.terminals, self.locks):
            checked_output_path(self.root, path)
            path.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def lock(self, attempt_id: str) -> Iterator[None]:
        path = self.locks / f"{_key(attempt_id)}.lock"
        atomic_write_immutable(path, b"")
        descriptor = open_file_no_follow(path, os.O_RDONLY)
        with os.fdopen(descriptor, "a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def claim(self, attempt_id: str, request_sha256: str) -> tuple[str, CanAttemptRecord]:
        current = self.load(attempt_id)
        if current is not None:
            resolution = "matched" if current.request_sha256 == request_sha256 else "conflict"
            return resolution, current
        record = make_attempt_record(
            attempt_id=attempt_id, request_sha256=request_sha256, state="claimed",
            terminal_uri=None, terminal_sha256=None,
        )
        self._save(record)
        return "created", record

    def transition(self, record: CanAttemptRecord, state: str) -> CanAttemptRecord:
        updated = make_attempt_record(
            attempt_id=record.attempt_id, request_sha256=record.request_sha256,
            state=state, terminal_uri=None, terminal_sha256=None,
        )
        self._save(updated)
        return updated

    def publish(self, record: CanAttemptRecord, terminal: dict) -> CanAttemptRecord:
        content = canonical_json(terminal)
        digest = hashlib.sha256(content).hexdigest()
        path = self.terminals / f"terminal-{digest}.json"
        atomic_write_immutable(path, content)
        state = "succeeded" if terminal.get("status") == "completed" else "failed"
        updated = make_attempt_record(
            attempt_id=record.attempt_id, request_sha256=record.request_sha256,
            state=state, terminal_uri=path.resolve().as_uri(), terminal_sha256=digest,
        )
        self._save(updated)
        return updated

    def load(self, attempt_id: str) -> CanAttemptRecord | None:
        path = self._record_path(attempt_id)
        try:
            content = read_bytes_no_follow(path)
        except FileNotFoundError:
            return None
        record = CanAttemptRecord.model_validate_json(content)
        if record.attempt_id != attempt_id:
            raise ValueError("attempt record identity mismatch")
        return record

    def load_terminal(self, record: CanAttemptRecord) -> dict:
        if not record.terminal_uri or not record.terminal_sha256:
            raise ValueError("attempt has no terminal output")
        from ..recipe import path_from_uri
        path = path_from_uri(record.terminal_uri)
        if path.parent != self.terminals or path.name != f"terminal-{record.terminal_sha256}.json":
            raise ValueError("attempt terminal pointer is outside its immutable store")
        content = read_bytes_no_follow(path)
        if hashlib.sha256(content).hexdigest() != record.terminal_sha256:
            raise ValueError("attempt terminal digest mismatch")
        value = json.loads(content)
        if content != canonical_json(value):
            raise ValueError("attempt terminal bytes are not canonical")
        return value

    def _save(self, record: CanAttemptRecord) -> None:
        atomic_write(
            self._record_path(record.attempt_id),
            canonical_json(record.model_dump(mode="json")),
        )

    def _record_path(self, attempt_id: str) -> Path:
        return self.attempts / f"{_key(attempt_id)}.json"


def _key(attempt_id: str) -> str:
    if not attempt_id.strip():
        raise ValueError("attempt_id is required")
    return hashlib.sha256(attempt_id.encode()).hexdigest()


__all__ = ["LocalCanAttemptStore"]

"""Shared helpers for the UDS bind-mount sweeper test modules."""

from __future__ import annotations

import json
import shutil
import socket
import tempfile
from pathlib import Path

import pytest


def _inspect_state(
    container_id: str, *, status: str = "exited",
    finished: str = "2026-09-30T10:00:00Z",
    started: str = "2026-09-30T09:00:00Z",
    labels: dict[str, str] | None = None,
) -> str:
    return "\t".join((
        container_id, status, finished, started,
        json.dumps(labels if labels is not None else {"factory.sandbox": "true"}),
    ))


@pytest.fixture
def short_tmp():
    # macOS AF_UNIX paths cap at ~104 chars; pytest tmp_path is far too long.
    directory = tempfile.mkdtemp(dir="/tmp")
    try:
        yield Path(directory)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def _make_socket(directory: Path) -> str:
    sock_path = str(directory / "mcp.sock")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    server.listen(1)
    return sock_path


_PS_LINES = (
    f"{'a' * 64}\tExited (0) 1 minute ago\t"
    "factory.sandbox=true,factory.workload=workload:launch-1\n"
    f"{'b' * 64}\tDead\tfactory.sandbox=true\n"
)

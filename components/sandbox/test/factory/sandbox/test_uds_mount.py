"""Tests for the workload UDS bind-mount helper: socket validation and mount assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.sandbox.runtime.adapters import uds_mount

from ._uds_mount_helpers import _make_socket, short_tmp  # noqa: F401


def test_validate_socket_accepts_real_socket(short_tmp: Path) -> None:
    uds_mount.validate_socket(_make_socket(short_tmp))  # no raise


def test_validate_socket_rejects_missing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        uds_mount.validate_socket(str(tmp_path / "nope.sock"))


def test_validate_socket_rejects_regular_file(tmp_path: Path) -> None:
    regular = tmp_path / "plain.txt"
    regular.write_text("not a socket")
    with pytest.raises(ValueError, match="not a socket"):
        uds_mount.validate_socket(str(regular))


def test_build_mount_args_proxy_socket(short_tmp: Path) -> None:
    sock = _make_socket(short_tmp)
    args = uds_mount.build_mount_args({"proxy_socket": sock})
    assert args == ["-v", f"{sock}:{uds_mount.CANONICAL_PROXY_SOCKET}"]


def test_build_mount_args_generic_mounts_and_readonly() -> None:
    args = uds_mount.build_mount_args({
        "mounts": [
            {"source": "/host/a", "target": "/ctr/a"},
            {"source": "/host/b", "target": "/ctr/b", "read_only": True},
        ],
    })
    assert args == ["-v", "/host/a:/ctr/a", "-v", "/host/b:/ctr/b:ro"]


def test_build_mount_args_missing_socket_fails_loud() -> None:
    with pytest.raises(ValueError, match="not found"):
        uds_mount.build_mount_args({"proxy_socket": "/does/not/exist.sock"})


def test_proxy_env_forces_canonical_target(short_tmp: Path) -> None:
    sock = _make_socket(short_tmp)
    assert uds_mount.proxy_env({"proxy_socket": sock}) == {
        "MCP_PROXY_SOCKET": uds_mount.CANONICAL_PROXY_SOCKET,
    }
    assert uds_mount.proxy_env({}) == {}

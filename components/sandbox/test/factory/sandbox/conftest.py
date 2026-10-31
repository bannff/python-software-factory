"""Sandbox test fixtures shared by adapter and boundary suites."""

import pytest
from factory.sandbox.runtime.adapters import docker_adapter


@pytest.fixture(autouse=True)
def _use_temporary_peer_lock_dir(tmp_path, monkeypatch) -> None:
    """Keep host lock-file tests isolated and writable in restricted runners."""
    monkeypatch.setattr(
        docker_adapter, "_PEER_NETWORK_LOCK_DIR", tmp_path / "peer-locks",
    )

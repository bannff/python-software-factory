"""Direct Docker adapter secret-guard and entrypoint-trust tests."""

from __future__ import annotations


import pytest

from factory.sandbox.runtime.adapters import docker_adapter
from factory.sandbox.runtime.adapters.docker_adapter import DockerAdapter

from ._secret_mount_helpers import PINNED_IMAGE

@pytest.mark.parametrize("marker", [(0, "true\n", ""), (1, "", "unavailable")])
@pytest.mark.asyncio
async def test_direct_docker_file_ops_deny_secret_or_unverifiable_container(
    monkeypatch, marker,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command, timeout=30):  # noqa: ANN001
        calls.append(command)
        if command[:3] == ["docker", "inspect", "--format"]:
            return marker
        raise AssertionError("secret container must not receive docker cp/exec")

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    adapter = DockerAdapter()
    assert (await adapter.upload_file("edge-lab", "/tmp/x", "/tmp/y"))["success"] is False
    assert (await adapter.download_file("edge-lab", "/tmp/x", "/tmp/y"))["success"] is False
    assert await adapter.list_files("edge-lab") == []
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_direct_docker_file_ops_continue_for_verified_nonsecret_container(
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command, timeout=30):  # noqa: ANN001
        calls.append(command)
        if command[:3] == ["docker", "inspect", "--format"]:
            return 0, "<no value>\n", ""
        if command[:2] == ["docker", "cp"]:
            return 0, "", ""
        if command[:2] == ["docker", "exec"]:
            return 0, "total 0\n", ""
        raise AssertionError(f"Unexpected Docker call: {command}")

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    adapter = DockerAdapter()
    assert (await adapter.upload_file("ordinary", "/tmp/x", "/tmp/y"))["success"]
    assert (await adapter.download_file("ordinary", "/tmp/y", "/tmp/x"))["success"]
    assert isinstance(await adapter.list_files("ordinary"), list)
    assert sum(call[:2] == ["docker", "cp"] for call in calls) == 2
    assert sum(call[:2] == ["docker", "exec"] for call in calls) == 1


@pytest.mark.asyncio
async def test_direct_docker_secret_provision_rejects_wrong_local_image_id_before_mutation(
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command, timeout=30):  # noqa: ANN001
        calls.append(command)
        return 0, "sha256:" + "b" * 64 + "\n", ""

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    with pytest.raises(ValueError, match="local image ID"):
        await DockerAdapter().provision({
            "image": PINNED_IMAGE, "entrypoint": ["/usr/local/bin/runner"],
            "secret_mounts": [object()], "replace_existing": False,
        })
    assert calls == [["docker", "image", "inspect", "--format", "{{.Id}}", PINNED_IMAGE]]


@pytest.mark.parametrize("image_entrypoint", [
    "null\n", "[]\n", '"/usr/local/bin/runner"\n',
    '["sh", "-c", "cat /run/secrets/ditto-offline-license"]\n',
    '["/bin/sh", "-c", "cat /run/secrets/ditto-offline-license"]\n',
    '["runner", "run"]\n',
    '["/usr/local/bin/runner", "--eval", "payload"]\n',
    "not json\n",
])
@pytest.mark.asyncio
async def test_secret_provision_rejects_untrusted_image_entrypoint_before_mutation(
    monkeypatch, image_entrypoint,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command, timeout=30):  # noqa: ANN001
        calls.append(command)
        if command[:3] != ["docker", "image", "inspect"]:
            raise AssertionError("Container or network mutation reached")
        if "{{.Id}}" in command:
            return 0, PINNED_IMAGE + "\n", ""
        return 0, image_entrypoint, ""

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    with pytest.raises(ValueError, match="image ENTRYPOINT"):
        await DockerAdapter().provision({
            "image": PINNED_IMAGE, "entrypoint": ["run"],
            "secret_mounts": [object()], "replace_existing": False,
        })
    assert len(calls) == 2
    assert all(command[:3] == ["docker", "image", "inspect"] for command in calls)


@pytest.mark.asyncio
async def test_secret_provision_fails_closed_if_image_entrypoint_inspect_fails(
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command, timeout=30):  # noqa: ANN001
        calls.append(command)
        if command[:3] != ["docker", "image", "inspect"]:
            raise AssertionError("Container or network mutation reached")
        if "{{.Id}}" in command:
            return 0, PINNED_IMAGE + "\n", ""
        return 1, "", "Docker metadata unavailable"

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    with pytest.raises(ValueError, match="image ENTRYPOINT"):
        await DockerAdapter().provision({
            "image": PINNED_IMAGE, "entrypoint": ["run"],
            "secret_mounts": [object()], "replace_existing": False,
        })
    assert len(calls) == 2

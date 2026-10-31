"""Profile-validation and secret-ref resolution tests for sandbox secret mounts."""
from __future__ import annotations

import json
import subprocess

import pytest
from pydantic import ValidationError

from factory.sandbox.runtime.adapters import secret_mounts
from factory.sandbox.runtime.adapters import docker_adapter
from factory.sandbox.runtime.profiles import SandboxProfile
from factory.sandbox.runtime.models import SandboxConfig
from factory.sandbox.runtime.provision_context import build_provision_context
from ._secret_mount_helpers import PINNED_IMAGE

def test_profile_accepts_only_named_secret_refs() -> None:
    profile = SandboxProfile(
        name="edge-lab", image="python:3.11-slim",
        secret_refs=["ditto-offline-license"],
    )
    assert profile.secret_refs == ["ditto-offline-license"]
    assert "secret_refs" in profile.model_dump()

    for invalid in ("/host/license", "../license", "ditto-admin-token"):
        with pytest.raises(ValidationError):
            SandboxProfile(
                name="bad", image="python:3.11-slim", secret_refs=[invalid],
            )

    with pytest.raises(ValidationError):
        SandboxProfile.model_validate({
            "name": "bad", "image": "python:3.11-slim",
            "secret_mounts": [{"source": "/host/license", "target": "/tmp/license"}],
            })
    with pytest.raises(ValidationError):
        SandboxProfile(
            name="duplicate", image="python:3.11-slim",
            secret_refs=["ditto-offline-license", "ditto-offline-license"],
        )


def test_resolve_secret_ref_requires_regular_host_file_without_echoing_path(tmp_path) -> None:
    secret = tmp_path / "license.sentinel"
    secret.write_text("SYNTHETIC_SECRET_SENTINEL")
    resolved = secret_mounts.resolve_secret_mounts(
        ["ditto-offline-license"],
        {secret_mounts.DITTO_LICENSE_ENV: str(secret)},
    )
    assert len(resolved) == 1
    assert resolved[0].source == secret.resolve()
    assert resolved[0].target == secret_mounts.DITTO_LICENSE_TARGET

    with pytest.raises(ValueError) as missing:
        secret_mounts.resolve_secret_mounts(["ditto-offline-license"], {})
    assert str(secret) not in str(missing.value)

    with pytest.raises(ValueError) as directory:
        secret_mounts.resolve_secret_mounts(
            ["ditto-offline-license"],
            {secret_mounts.DITTO_LICENSE_ENV: str(tmp_path)},
        )
    assert str(tmp_path) not in str(directory.value)


def test_build_mount_args_uses_fixed_target_and_read_only_bind(tmp_path) -> None:
    source = tmp_path / "license"
    source.write_text("SYNTHETIC_SECRET_SENTINEL")
    mounts = secret_mounts.resolve_secret_mounts(
        ["ditto-offline-license"],
        {secret_mounts.DITTO_LICENSE_ENV: str(source)},
    )

    args = secret_mounts.build_secret_mount_args(mounts)
    assert args == [
        "--mount",
        f"type=bind,source={source.resolve()},target={secret_mounts.DITTO_LICENSE_TARGET},readonly",
    ]


def test_docker_cli_does_not_inherit_host_secret_path(monkeypatch) -> None:
    host_path = "/private/host/license"
    monkeypatch.setenv(secret_mounts.DITTO_LICENSE_ENV, host_path)
    captured: dict = {}

    def fake_run(command, **kwargs):  # noqa: ANN001
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    docker_adapter._run(["docker", "info"])
    assert secret_mounts.DITTO_LICENSE_ENV not in captured["env"]
    assert host_path not in captured["env"].values()


def test_profile_resolution_keeps_host_path_out_of_metadata(tmp_path, monkeypatch) -> None:
    source = tmp_path / "license"
    source.write_text("SYNTHETIC_SECRET_SENTINEL")
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "edge-lab.yaml").write_text(
        f"image: {PINNED_IMAGE}\n"
        "container_name: edge-lab\n"
        "replace_existing: false\n"
        "entrypoint: [run]\n"
        "peer_network: {network_id: secret-lab, alias: edge-lab, port: 4321, internal: true}\n"
        "secret_refs: [ditto-offline-license]\n"
    )
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(profiles))
    monkeypatch.setenv(secret_mounts.DITTO_LICENSE_ENV, str(source))

    config, metadata, _ = build_provision_context(SandboxConfig(), "edge-lab")
    assert config["secret_mounts"][0].source == source.resolve()
    serialized_metadata = json.dumps(metadata)
    assert str(source) not in serialized_metadata
    assert "SYNTHETIC_SECRET_SENTINEL" not in serialized_metadata
    assert "secret_mounts" not in metadata


def test_secret_profile_must_not_replace_existing_container(tmp_path, monkeypatch) -> None:
    source = tmp_path / "license"
    source.write_text("SYNTHETIC_SECRET_SENTINEL")
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "unsafe.yaml").write_text(
        f"image: {PINNED_IMAGE}\n"
        "secret_refs: [ditto-offline-license]\n"
    )
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(profiles))
    monkeypatch.setenv(secret_mounts.DITTO_LICENSE_ENV, str(source))
    with pytest.raises(ValueError, match="must not replace"):
        build_provision_context(SandboxConfig(), "unsafe")


@pytest.mark.parametrize(
    "network,override",
    [
        ("", None),
        (
            "peer_network: {network_id: secret-lab, alias: edge-lab, port: 4321, "
            "internal: false}\n",
            None,
        ),
        (
            "peer_network: {network_id: secret-lab, alias: edge-lab, port: 4321, "
            "internal: true}\n",
            {
                "network_id": "secret-lab", "alias": "edge-lab",
                "port": 4321, "internal": False,
            },
        ),
    ],
)
def test_secret_profile_requires_explicit_internal_peer_network(
    tmp_path, monkeypatch, network, override,
) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "secret.yaml").write_text(
        f"image: {PINNED_IMAGE}\n"
        "replace_existing: false\n"
        "entrypoint: [/usr/local/bin/ditto-runner]\n"
        f"{network}"
        "secret_refs: [ditto-offline-license]\n"
    )
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(profiles))
    with pytest.raises(ValueError, match="require an internal peer network"):
        build_provision_context(SandboxConfig(), "secret", peer_network=override)


@pytest.mark.parametrize(
    "trusted_entrypoint,setup_commands,message",
    [
        ("", "", "trusted fixed entrypoint"),
        (
            "entrypoint: [/usr/local/bin/ditto-runner]\n",
            'setup_commands: ["pip install x"]\n',
            "cannot define setup_commands",
        ),
    ],
)
def test_secret_profile_requires_trusted_noninteractive_entrypoint(
    tmp_path, monkeypatch, trusted_entrypoint, setup_commands, message,
) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "secret.yaml").write_text(
        f"image: {PINNED_IMAGE}\n"
        "replace_existing: false\n"
        f"{trusted_entrypoint}"
        "peer_network: {network_id: secret-lab, alias: edge-lab, port: 4321, internal: true}\n"
        f"{setup_commands}"
        "secret_refs: [ditto-offline-license]\n"
    )
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(profiles))
    with pytest.raises(ValueError, match=message):
        build_provision_context(SandboxConfig(), "secret")



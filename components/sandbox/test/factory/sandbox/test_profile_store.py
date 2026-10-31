"""Tests for YAML-backed sandbox profile loading."""
from __future__ import annotations

import pytest

from factory.sandbox.runtime import profile_store
from factory.sandbox.runtime.profiles import (
    BUILTIN_PROFILES,
    list_profiles,
    resolve_profile,
)


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    return tmp_path


def _write(profiles_dir, name: str, body: str) -> None:
    (profiles_dir / f"{name}.yaml").write_text(body)


def test_load_yaml_profile_roundtrip(profiles_dir) -> None:
    _write(
        profiles_dir,
        "rusty",
        "image: rust:1-slim\nshell: /bin/bash\n"
        'entrypoint: ["sleep", "infinity"]\nsetup_commands: ["rustup component add clippy"]\n',
    )
    p = profile_store.load_yaml_profile("rusty")
    assert p is not None
    assert p.name == "rusty"  # backfilled from filename
    assert p.image == "rust:1-slim"
    assert p.entrypoint == ["sleep", "infinity"]
    assert p.setup_commands == ["rustup component add clippy"]


def test_missing_yaml_profile_returns_none(profiles_dir) -> None:
    assert profile_store.load_yaml_profile("nope") is None


def test_resolve_prefers_builtin_over_yaml(profiles_dir) -> None:
    # A YAML file shadowing a builtin name must not override the builtin.
    _write(profiles_dir, "webgoat", "image: evil/override:latest\n")
    p = resolve_profile("webgoat")
    assert p.image == BUILTIN_PROFILES["webgoat"].image


def test_resolve_falls_back_to_yaml(profiles_dir) -> None:
    _write(profiles_dir, "rust-sdk", "image: rust:1-slim\n")
    assert resolve_profile("rust-sdk").image == "rust:1-slim"


def test_list_profiles_merges_builtins_and_yaml(profiles_dir) -> None:
    _write(profiles_dir, "custom-one", "image: alpine\n")
    names = list_profiles()
    assert "custom-one" in names
    assert all(b in names for b in BUILTIN_PROFILES)


def test_unknown_profile_raises(profiles_dir) -> None:
    with pytest.raises(ValueError, match="Unknown profile"):
        resolve_profile("totally-unknown")


@pytest.mark.parametrize("bad", ["../escape", "/etc/passwd", "a/b", "..", "name with space"])
def test_name_guard_rejects_path_escape(profiles_dir, bad) -> None:
    # Guard rejects invalid/traversing names by returning None (no load, no escape).
    assert profile_store.load_yaml_profile(bad) is None


def test_non_mapping_yaml_raises(profiles_dir) -> None:
    _write(profiles_dir, "listy", "- just\n- a\n- list\n")
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        profile_store.load_yaml_profile("listy")


def test_typo_key_fails_loud(profiles_dir) -> None:
    # extra="forbid": a misspelled key must raise, not silently drop.
    _write(profiles_dir, "typo", "image: rust:1-slim\nsetup_command: [echo hi]\n")
    with pytest.raises(ValueError):
        profile_store.load_yaml_profile("typo")

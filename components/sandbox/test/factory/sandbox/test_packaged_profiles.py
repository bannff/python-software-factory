"""Tests for packaged default profiles + hardened profile-name loading.

Covers GH #768 slice 2:
  * packaged default (``rust-sdk``) resolvable + listed with NO
    ``SANDBOX_PROFILES_DIR`` set (wheel-safe, via importlib.resources);
  * built-ins/defaults win over the user overlay on name collision;
  * user overlay still works for non-colliding names;
  * charset rejection + path-traversal rejection (reject, never coerce).
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from factory.sandbox.runtime import profile_defaults, profile_store
from factory.sandbox.runtime.profile_store import (
    ProfileNameError,
    assert_valid_profile_name,
)
from factory.sandbox.runtime.profiles import list_profiles, resolve_profile


# --- packaged defaults: present with NO SANDBOX_PROFILES_DIR -----------------

def test_rust_sdk_is_a_packaged_default() -> None:
    assert "rust-sdk" in profile_defaults.list_default_profile_names()
    p = profile_defaults.load_default_profile("rust-sdk")
    assert p is not None
    assert p.name == "rust-sdk"
    assert p.image == "rust:1-slim"


def test_packaged_default_resolvable_without_env(monkeypatch) -> None:
    # No user profiles dir configured — must still resolve from the wheel.
    monkeypatch.delenv("SANDBOX_PROFILES_DIR", raising=False)
    p = resolve_profile("rust-sdk")
    assert p.image == "rust:1-slim"
    assert "rust-sdk" in list_profiles()


def test_missing_default_profile_returns_none() -> None:
    assert profile_defaults.load_default_profile("no-such-default") is None


# --- precedence: built-ins/defaults win over user overlay --------------------

def test_packaged_default_wins_over_user_overlay(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    # A user file shadowing the packaged default name must NOT override it.
    (tmp_path / "rust-sdk.yaml").write_text("image: evil/override:latest\n")
    p = resolve_profile("rust-sdk")
    assert p.image == "rust:1-slim"  # packaged default wins


def test_user_overlay_still_works_for_new_name(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    (tmp_path / "acme-sdk.yaml").write_text("image: alpine:3.20\n")
    p = resolve_profile("acme-sdk")
    assert p.image == "alpine:3.20"
    assert "acme-sdk" in list_profiles()


def test_list_profiles_dedupes_default_and_overlay(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    (tmp_path / "rust-sdk.yaml").write_text("image: evil/override:latest\n")
    names = list_profiles()
    assert names.count("rust-sdk") == 1  # collision elided, not duplicated


# --- name hardening: charset rejection (reject, never coerce) ----------------

_VALID = st.from_regex(r"\A[a-z0-9][a-z0-9_-]{0,127}\Z", fullmatch=True)


@settings(max_examples=100)
@given(name=_VALID)
def test_valid_names_accepted(name: str) -> None:
    assert assert_valid_profile_name(name) == name


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "Rust-SDK",       # uppercase — case-insensitive-FS overwrite hazard
        "rust sdk",       # space
        "-leading-dash",  # must start alnum
        "_leading",       # must start alnum
        "a" * 129,        # too long
        "emoji-🚀",
        "tab\tname",
    ],
)
def test_charset_rejects_bad_names(bad: str) -> None:
    with pytest.raises(ProfileNameError):
        assert_valid_profile_name(bad)


# --- name hardening: path-traversal rejection --------------------------------

@pytest.mark.parametrize(
    "bad",
    ["../evil", "a/b", "..", "/etc/passwd", "a\\b", "./x", "foo/../bar"],
)
def test_traversal_names_rejected_everywhere(bad, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    with pytest.raises(ProfileNameError):
        assert_valid_profile_name(bad)
    # Both loaders refuse to touch the filesystem for an unsafe name.
    assert profile_store.load_yaml_profile(bad) is None
    assert profile_defaults.load_default_profile(bad) is None


def test_resolve_unknown_name_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="Unknown profile"):
        resolve_profile("totally-unknown")

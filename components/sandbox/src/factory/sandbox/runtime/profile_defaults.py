"""Packaged default sandbox profiles — always present, wheel-safe.

These ``<name>.yaml`` files live inside the brick under
``runtime/profiles_data/`` and are read via ``importlib.resources`` (NOT by
filesystem path) so they resolve identically from a source checkout and from
an installed wheel, regardless of ``SANDBOX_PROFILES_DIR``.

Precedence lives in ``profiles.py``: code built-ins and these packaged defaults
win over the user overlay (mirrors the persona registry's built-ins-win rule).
"""
from __future__ import annotations

from importlib.resources import files

from .profile_store import (
    AuthoringError,
    assert_valid_profile_name,
    parse_profile_yaml,
)
from .profiles import SandboxProfile

_DATA_PKG = "factory.sandbox.runtime.profiles_data"
_SUFFIX = ".yaml"


def list_default_profile_names() -> list[str]:
    """Return the names of every packaged default profile."""
    names: list[str] = []
    for entry in files(_DATA_PKG).iterdir():
        entry_name = entry.name
        if entry_name.endswith(_SUFFIX) and entry.is_file():
            names.append(entry_name[: -len(_SUFFIX)])
    return sorted(names)


def load_default_profile(name: str) -> SandboxProfile | None:
    """Load a packaged default profile by name, or ``None`` if absent/unsafe."""
    try:
        assert_valid_profile_name(name)
    except AuthoringError:
        return None
    resource = files(_DATA_PKG).joinpath(f"{name}{_SUFFIX}")
    if not resource.is_file():
        return None
    return parse_profile_yaml(name, resource.read_text(encoding="utf-8"))

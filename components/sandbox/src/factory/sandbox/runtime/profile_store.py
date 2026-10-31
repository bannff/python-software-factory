"""YAML-backed user sandbox profile loading + shared name hardening.

Profile sources (merged in ``profiles.py``):
  1. code ``profiles.BUILTIN_PROFILES``
  2. packaged defaults shipped with the brick (``profile_defaults.py``)
  3. user ``<name>.yaml`` files under ``SANDBOX_PROFILES_DIR``
     (default: ``projects/companion_x/sandbox-profiles``), loaded on demand.

This module owns (a) user-YAML loading and (b) the security-sensitive
profile-name guard reused by the packaged-default loader. Keeping it separate
from ``profiles.py`` preserves SRP and the <200 LOC budget.

Name hardening (bd:python-factory-67qvz precedent — reject, never coerce):
  * charset-locked to ``^[a-z0-9][a-z0-9_-]{0,127}$``. Lowercase-only closes
    the case-insensitive-filesystem overwrite hazard (``Foo`` vs ``foo``).
  * traversal-safe: the charset already forbids ``/``, ``\\``, ``.`` (so ``..``,
    absolute paths, and separators are rejected); ``_assert_within_root`` is a
    defense-in-depth check that the resolved path stays inside the dir.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from ..authoring import AuthoringError, _assert_within_root
from .profiles import SandboxProfile

_DEFAULT_PROFILES_DIR = "projects/companion_x/sandbox-profiles"

# Lowercase-only, traversal-hostile stem. Distinct from authoring's `_ID_RE`
# (which permits uppercase for template ids); profile names map to filenames on
# a possibly case-insensitive FS, so we lock case here.
_PROFILE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")


class ProfileNameError(AuthoringError):
    """Raised when a profile name is unsafe (bad charset or path traversal)."""


def assert_valid_profile_name(name: str) -> str:
    """Validate a profile name is a safe plain stem; return it or raise.

    Rejects (never coerces) anything that is not lowercase alnum/``_``/``-``,
    which also rejects ``/``, ``\\``, ``..`` and every path separator.
    """
    if not isinstance(name, str) or not _PROFILE_NAME_RE.match(name):
        raise ProfileNameError(
            "Invalid profile name; expected [a-z0-9][a-z0-9_-]{0,127} "
            "(lowercase, no path separators)"
        )
    return name


def profiles_dir() -> Path:
    """Resolve the directory that holds user-defined profile YAML files."""
    return Path(os.environ.get("SANDBOX_PROFILES_DIR", _DEFAULT_PROFILES_DIR))


def _profile_path(name: str) -> Path:
    """Validate ``name`` and return its guarded ``<dir>/<name>.yaml`` path."""
    assert_valid_profile_name(name)
    root = profiles_dir()
    path = root / f"{name}.yaml"
    _assert_within_root(root, path)  # defense-in-depth against traversal
    return path


def parse_profile_yaml(name: str, text: str) -> SandboxProfile:
    """Parse YAML ``text`` into a ``SandboxProfile``, backfilling ``name``."""
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Profile {name!r} must be a YAML mapping")
    data.setdefault("name", name)
    return SandboxProfile(**data)


def load_yaml_profile(name: str) -> SandboxProfile | None:
    """Load a user-defined profile by name, or ``None`` if absent/unsafe."""
    try:
        path = _profile_path(name)
    except AuthoringError:
        return None  # unsafe name — refuse to touch the filesystem
    if not path.exists():
        return None
    return parse_profile_yaml(name, path.read_text())


def list_yaml_profile_names() -> list[str]:
    """Return the names of all user-defined YAML profiles on disk."""
    root = profiles_dir()
    if not root.exists():
        return []
    return sorted(p.stem for p in root.glob("*.yaml"))

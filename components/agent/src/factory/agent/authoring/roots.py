"""Durable, layered on-disk roots for Agent authoring.

Every authoring write targets an operator-controlled directory instead of
the installed package (or a throw-away temp dir). Resolution is pure and
cheap so it is safe at import/registration time; ``ensure_root`` performs
the ``mkdir`` and raises ``AuthoringRootUnavailable`` — writes call it (and
degrade to a typed failure) so a bad root can never take the read-only
tools down with it.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Literal

ROOT_SPECS: dict[str, tuple[str, str]] = {
    "config": ("FACTORY_AGENT_CONFIG_DIR", ".storage/agent-config"),
    "skills": ("FACTORY_AGENT_SKILLS_DIR", ".storage/agent-skills"),
    "steering": ("FACTORY_AGENT_STEERING_DIR", ".storage/agent-steering"),
}


class AuthoringRootUnavailable(RuntimeError):
    """A durable authoring root is unusable for writing."""

    def __init__(self, variable: str, path: Path, cause: object) -> None:
        super().__init__(f"{variable}={path} is unavailable: {cause}")
        self.variable = variable
        self.path = path
        self.cause = cause


@dataclass(frozen=True)
class AuthoringRoot:
    """One resolved authoring root; ``source`` says who chose the path."""

    kind: str
    variable: str
    path: Path
    source: Literal["env", "default"]
    #: The CONFIGURED path was a symlink (resolved away in ``path``).
    symlinked: bool = False


def resolve_root(kind: str) -> AuthoringRoot:
    """Resolve one root without touching the filesystem."""
    variable, default = ROOT_SPECS[kind]
    configured = os.environ.get(variable, "").strip()
    if configured:
        raw = Path(configured).expanduser()
        return AuthoringRoot(kind, variable, raw.resolve(), "env", raw.is_symlink())
    return AuthoringRoot(kind, variable, Path(default).expanduser().resolve(), "default")


def ensure_root(kind: str, *, refuse_symlink: bool = False) -> AuthoringRoot:
    """Resolve one root and create it, raising ``AuthoringRootUnavailable``.

    ``refuse_symlink`` keeps a symlinked skills/steering root fail-closed, so a
    configured link can never redirect an authoring write somewhere else.
    """
    root = resolve_root(kind)
    if refuse_symlink and root.symlinked:
        raise AuthoringRootUnavailable(root.variable, root.path, "the configured path is a symlink")
    try:
        root.path.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as error:
        raise AuthoringRootUnavailable(root.variable, root.path, error) from error
    return root


def config_root_for(agent: Any) -> Path:
    """The config root an agent writes to.

    Its own ``config_dir`` when it has one, else the durable default root.
    Registration must never require that attribute, because tool catalogs are
    also built from stand-in agents (aggregators, harnesses).
    """
    return Path(str(getattr(agent, "config_dir", "") or resolve_root("config").path))


def packaged_skills_root() -> Path:
    """Read-only packaged built-in skills shipped with the brick."""
    return Path(__file__).resolve().parents[1] / "skills"


__all__ = [
    "AuthoringRoot", "AuthoringRootUnavailable", "ROOT_SPECS", "config_root_for",
    "ensure_root", "packaged_skills_root", "resolve_root",
]

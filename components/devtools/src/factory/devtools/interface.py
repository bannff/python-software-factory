"""Public Devtools brick interface."""
import os
from pathlib import Path

from .runtime.path_resolver import PathRefused, bind_project
from .runtime.runtime import DevtoolsRuntime as Runtime
from .server import create_mcp_server as create_server


def _allowed_roots() -> tuple[Path, ...]:
    raw = os.getenv("COMPANION_X_PROJECT_ALLOWED_ROOTS")
    return tuple(Path(value) for value in raw.split(os.pathsep) if value) \
        if raw else (Path.cwd().resolve().parent,)


def validate_project(
    tenant_id: str, owner_id: str, session_id: str, candidate: str,
) -> str:
    return bind_project(
        tenant_id, owner_id, session_id, candidate, _allowed_roots(),
    ).root


def list_allowed_project_roots() -> list[str]:
    """The configured project roots, as absolute path strings, for a picker UI."""
    return [str(root.resolve()) for root in _allowed_roots()]


# bind_project needs identity fields; admission does not depend on them.
_PICKER_IDS = ("picker", "picker", "picker")


def list_projects() -> list[str]:
    """Admissible projects: each allowed root and its direct children that `bind_project` accepts.

    Admission is delegated to `bind_project` so the picker can never offer a
    choice that session/crew creation would refuse.
    """
    roots = _allowed_roots()
    found: set[str] = set()
    for root in roots:
        try:
            candidates = [root, *(c for c in root.iterdir() if c.is_dir())]
        except OSError:
            continue
        for candidate in candidates:
            try:
                found.add(bind_project(*_PICKER_IDS, str(candidate), roots).root)
            except (PathRefused, OSError):
                continue
    return sorted(found)


__all__ = ["Runtime", "create_server", "list_allowed_project_roots", "list_projects", "validate_project"]

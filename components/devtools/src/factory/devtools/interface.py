"""Public Devtools brick interface."""
import os
from pathlib import Path

from .runtime.path_resolver import bind_project
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


__all__ = ["Runtime", "create_server", "list_allowed_project_roots", "validate_project"]

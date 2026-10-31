"""Safe, per-environment sandbox workspace creation."""

from __future__ import annotations

from pathlib import Path


def get_or_create_workspace(root: Path, env_id: str) -> Path:
    """Return a contained artifact directory or reject an unsafe environment ID."""
    if not env_id or Path(env_id).name != env_id or env_id in {".", ".."}:
        raise ValueError("env_id must be a single, non-empty path segment")
    base = root.resolve()
    workspace = (base / env_id / "artifacts").resolve()
    try:
        workspace.relative_to(base)
    except ValueError as exc:
        raise ValueError("env_id escapes the sandbox workspace root") from exc
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace

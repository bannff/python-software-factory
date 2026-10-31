"""Pure path resolver for RetroArch config/override/remap/preset files.

Precedence: game > content-dir > core > global (per R-RA §4).
"""

from __future__ import annotations

from pathlib import Path

from .models import Scope


def override_path(
    base_dir: Path,
    scope: Scope,
    *,
    core: str | None = None,
    game: str | None = None,
    kind: str,
) -> Path:
    """Return the file path for a given scope + kind.

    Args:
        base_dir: RetroArch config root (e.g. /config or /config/remaps).
        scope: GLOBAL, CORE, CONTENT_DIR, or GAME.
        core: Core name (required for CORE/CONTENT_DIR/GAME scopes).
        game: Game basename (required for GAME scope; used as content-dir for CONTENT_DIR).
        kind: File extension without dot (cfg, opt, rmp, slangp).

    Raises:
        ValueError: If required scope arguments are missing.
    """
    if scope == Scope.GLOBAL:
        return base_dir / f"global.{kind}"

    if core is None:
        raise ValueError(f"Scope {scope.value} requires 'core' argument")

    if scope == Scope.CORE:
        return base_dir / core / f"{core}.{kind}"

    if game is None:
        raise ValueError(f"Scope {scope.value} requires 'game' argument")

    if scope == Scope.CONTENT_DIR:
        return base_dir / core / f"{game}.{kind}"

    # GAME scope
    return base_dir / core / f"{game}.{kind}"

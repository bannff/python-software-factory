"""OpenArcade base entry point — wall composition + run helpers.

The base is a thin wiring layer. It does NOT re-implement the Flet app — that
lives in ``wall.app``. The base sets the right env vars, resolves the config
dir, and delegates to the wall's existing ``run()`` / ``run_web()`` entry
points so behavior is identical to ``projects/openarcade/wall/app.py``.

``build_app`` returns a ``ft.App`` object that callers (CI, kiosk installer,
tests) can launch in any view mode. ``run_wall`` is the convenience wrapper.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import flet as ft


def build_app(config_dir: Path | str | None = None) -> "ft.App":
    """Return a ``ft.App`` for the OpenArcade wall, pinned to ``config_dir``.

    The returned ``ft.App`` can be launched with any view (FLET_APP,
    FLET_APP_HIDDEN, WEB_BROWSER). When ``config_dir`` is None, the base
    resolves it from env / defaults.
    """
    import flet as ft

    from .env import resolve_config_dir
    from wall import app as wall_app

    resolved = resolve_config_dir(config_dir)
    os.environ["OPENARCADE_CONFIG_DIR"] = str(resolved)

    def _target(page: ft.Page) -> None:
        wall_app._target(page)  # noqa: SLF001 — wall module exposes the target

    assets_dir = os.environ.get("OPENARCADE_MEDIA_ROOT")
    kwargs: dict = {"target": _target}
    if assets_dir:
        kwargs["assets_dir"] = assets_dir
    return ft.App(**kwargs)


def run_wall(config_dir: Path | str | None = None) -> None:
    """Launch the native Flet wall window.

    Mirrors ``wall.app.run`` exactly, with the base's env contract applied
    (config dir resolution, no $HOME writes). Pass ``config_dir`` to override
    the default.
    """
    from .env import resolve_config_dir
    from wall import app as wall_app

    resolved = resolve_config_dir(config_dir)
    os.environ["OPENARCADE_CONFIG_DIR"] = str(resolved)
    wall_app.run()

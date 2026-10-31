"""Lean-deps contract: importing ``factory.openarcade`` must NOT pull ``fastmcp``.

The control-plane bricks' interface modules (launch, curator, library,
arcade_config, state) do not import fastmcp. The ui brick's interface does,
but the base never imports factory.ui directly — it goes through the wall,
which handles the Flet adapter itself. This test guards against accidental
regressions.

The MCP server lives at ``factory.openarcade.server`` and is built on the
native ``ToolCatalog`` (see ``factory.mcp_utils.runtime.tool_catalog``), not
fastmcp — the repo fully migrated to native MCP v2 and fastmcp is no longer a
dependency at all. Both the lean path (``import factory.openarcade``) and the
MCP server path (``factory.openarcade.server.create_mcp_server``) stay clean
of fastmcp.
"""

from __future__ import annotations

import sys

import pytest


@pytest.fixture
def clean_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove any pre-existing factory.* modules so the import is fresh."""
    for mod in list(sys.modules):
        if mod == "factory.openarcade" or mod.startswith("factory.openarcade."):
            monkeypatch.delitem(sys.modules, mod, raising=False)
    for mod in list(sys.modules):
        if mod.startswith("factory.") and (
            "openarcade" in mod or mod.startswith("factory.ui")
        ):
            monkeypatch.delitem(sys.modules, mod, raising=False)


def test_lean_import_does_not_pull_fastmcp(clean_imports: None) -> None:
    import factory.openarcade  # noqa: F401

    assert "fastmcp" not in sys.modules, (
        "factory.openarcade transitively imported fastmcp — the base must stay "
        "lean. Check that no factory.* import here goes through a module that "
        "imports fastmcp at module load time."
    )


def test_public_surface_resolves(clean_imports: None) -> None:
    from factory.openarcade import (  # noqa: F401
        ControlsVM,
        GameTile,
        GetStatusProbe,
        NciTransport,
        build_app,
        run_wall,
    )

    assert callable(build_app)
    assert callable(run_wall)
    assert GameTile is not None
    assert ControlsVM is not None
    assert NciTransport is not None
    assert GetStatusProbe is not None


def test_create_mcp_server_stays_lean_of_fastmcp(
    clean_imports: None, tmp_path, monkeypatch
) -> None:
    home_dir = tmp_path / "home"
    cfg_dir = tmp_path / "cfg"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("OPENARCADE_CONFIG_DIR", str(cfg_dir))
    from factory.openarcade.server import create_mcp_server

    server = create_mcp_server()
    assert server.name == "factory-openarcade"
    assert "fastmcp" not in sys.modules, (
        "factory.openarcade.server transitively imported fastmcp — the native "
        "MCP v2 ToolCatalog path must stay free of the retired fastmcp SDK."
    )

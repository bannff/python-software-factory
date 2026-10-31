"""Regression test for the Docker-vs-shell chat leak (bd: ag-ui composition root).

``projects/companion_x/main.py`` must build its Starlette app through the
``api`` base (``factory.api.main.create_app``), which mounts the
``CHAT_STREAMING``-aware AG-UI route. It must NOT fall back to
``factory.mcp_server.core.create_app``, which mounts the legacy blocking
``agent_reason`` + ``str(result)`` route that leaked raw ToolResult
envelopes (``{'schema_version': 'v1', 'ok': True, 'data': {...}}``) into
the chat UI. Both the Docker entrypoint (``entrypoint.sh`` -> ``main.py``)
and the local shell script (``scripts/companion-x-ui.sh`` -> ``main.py``)
invoke the exact same file, so a single fix here covers both launch paths.
"""
from __future__ import annotations

import ast
from pathlib import Path

MAIN_PY = Path(__file__).parents[1] / "main.py"


def test_main_imports_api_base_create_app_not_mcp_server_core():
    """``main()`` must import ``create_app`` from ``factory.api.main``."""
    tree = ast.parse(MAIN_PY.read_text())
    import_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "factory.api.main" in import_modules, (
        "main.py must build its app via factory.api.main.create_app "
        "(the composition root that mounts the streaming AG-UI route)"
    )
    assert "factory.mcp_server.core" not in import_modules, (
        "main.py must not import factory.mcp_server.core.create_app directly "
        "— that mounts the legacy non-streaming AG-UI route which stringifies "
        "raw ToolResult envelopes into chat text"
    )


def test_api_base_create_app_mounts_streaming_ag_ui_route():
    """The api base's create_app must register the CHAT_STREAMING-aware route.

    This is the route projects/companion_x/main.py now delegates to.
    """
    from factory.api.runtime.adapters import rest as rest_module

    source = Path(rest_module.__file__).read_text()
    assert "..ag_ui_routes import register_ag_ui_routes" in source


def test_companion_x_main_builds_app_with_streaming_ag_ui_route():
    """End-to-end: the exact app factory main.py calls must expose /ag-ui/run
    via the streaming-aware module, not the legacy mcp_server one."""
    from factory.api.main import create_app

    app = create_app()
    ag_ui_route = next(
        route for route in app.routes
        if getattr(route, "path", None) == "/ag-ui/run"
    )
    module = ag_ui_route.endpoint.__module__
    assert module == "factory.api.runtime.ag_ui_routes", (
        f"/ag-ui/run resolved to {module}, expected the streaming-aware "
        "factory.api.runtime.ag_ui_routes module"
    )

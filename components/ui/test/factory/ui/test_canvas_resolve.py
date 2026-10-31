"""Tests for the global-canvas authorization tool ``ui_resolve_canvas``.

Proves nonempty-authority gating, the closed allowlist, the fixed opaque
failure that never echoes input, the ``{view_id, authorized}`` egress shape, and
parity of the brick-side ``CanvasViewId`` Literal with the frontend TS union.
"""
from __future__ import annotations

import ast
import asyncio
import re
from pathlib import Path

from factory.mcp_utils.interface import (
    ToolCatalog, reset_envelope, set_envelope,
)
from factory.ui.mcp import canvas_resolve
from factory.ui.runtime.canvas_views import CANVAS_VIEW_IDS

_ENV = {"tenant_id": "t", "principal_id": "p"}
_ERROR = "canvas_view_not_found"


def _tool():
    catalog = ToolCatalog("test")
    canvas_resolve.register(catalog, lambda: None)
    return {t.name: t for t in asyncio.run(catalog.list_tools())}["ui_resolve_canvas"]


def _call(envelope, view_id):
    token = set_envelope(envelope) if envelope is not None else None
    try:
        return _tool().fn(view_id=view_id)
    finally:
        reset_envelope(token)


def test_authorized_view_returns_only_shape() -> None:
    result = _call(_ENV, "welcome")
    assert result.ok is True
    assert result.data.model_dump() == {"authorized": True, "view_id": "welcome"}


def test_taxonomy_is_deterministic() -> None:
    assert _tool().fn._mcp_category == "deterministic"


def test_unknown_view_is_opaque_without_echo() -> None:
    result = _call(_ENV, "nope-not-a-view")
    assert result.ok is False and result.error == _ERROR
    assert "nope-not-a-view" not in str(result.model_dump())


def test_missing_or_partial_authority_is_opaque() -> None:
    assert _call(None, "welcome").error == _ERROR
    assert _call({"tenant_id": "t"}, "welcome").error == _ERROR
    assert _call({"principal_id": "p"}, "welcome").error == _ERROR
    assert _call({"tenant_id": "", "principal_id": "p"}, "welcome").error == _ERROR


def test_every_allowlisted_view_authorizes() -> None:
    for view_id in CANVAS_VIEW_IDS:
        assert _call(_ENV, view_id).ok is True


def test_literal_matches_frontend_ts_union() -> None:
    ts = Path("frontends/next-dashboard/lib/types/workbench.ts").read_text()
    block = re.search(r"export type CanvasViewId\s*=\s*(.*?);", ts, re.S)
    assert block is not None
    ts_ids = set(re.findall(r'"([^"]+)"', block.group(1)))
    assert ts_ids == set(CANVAS_VIEW_IDS)


def test_canvas_views_module_has_no_ui_runtime_imports() -> None:
    tree = ast.parse(Path(
        "components/ui/src/factory/ui/runtime/canvas_views.py").read_text())
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert all(m in (None, "typing", "__future__") for m in imports)

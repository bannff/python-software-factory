"""Canary: AG-UI ACTIVITY enum + dispatcher version pin (bd-6zyg).

Reads ``frontends/next-dashboard/node_modules/@ag-ui/core/dist/
index.d.ts`` and asserts the ``ACTIVITY_SNAPSHOT`` / ``ACTIVITY_DELTA``
enum values match the strings emitted by ``AGUIEventType``. This
catches a future ``@ag-ui/core`` rename before it ships to prod.

Pinned versions (must match exact-pin in ``package.json``):
  * ``@ag-ui/[email protected]``
  * ``@copilotkit/[email protected]``
  * ``@copilotkitnext/[email protected]``
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[5]
NODE_MODULES = REPO_ROOT / "frontends" / "next-dashboard" / "node_modules"
AG_UI_TYPES = NODE_MODULES / "@ag-ui" / "core" / "dist" / "index.d.ts"
AG_UI_PKG = NODE_MODULES / "@ag-ui" / "core" / "package.json"
CK_PKG = NODE_MODULES / "@copilotkitnext" / "react" / "package.json"
DISPATCHER_MJS = (
    NODE_MODULES / "@copilotkitnext" / "react" / "dist"
    / "hooks" / "use-render-activity-message.mjs"
)
PACKAGE_JSON = REPO_ROOT / "frontends" / "next-dashboard" / "package.json"


def _skip_if_missing(p: Path) -> None:
    if not p.exists():
        pytest.skip(f"FE node_modules missing — run npm i in {p.parents[1]}")


def test_ag_ui_event_type_constants_match_types() -> None:
    _skip_if_missing(AG_UI_TYPES)
    text = AG_UI_TYPES.read_text()
    assert 'ACTIVITY_SNAPSHOT = "ACTIVITY_SNAPSHOT"' in text
    assert 'ACTIVITY_DELTA = "ACTIVITY_DELTA"' in text

    from factory.ui.runtime.ag_ui_mapper import AGUIEventType
    assert AGUIEventType.ACTIVITY_SNAPSHOT == "ACTIVITY_SNAPSHOT"
    assert AGUIEventType.ACTIVITY_DELTA == "ACTIVITY_DELTA"


def test_ag_ui_core_version_exact_pin() -> None:
    _skip_if_missing(AG_UI_PKG)
    pkg = json.loads(AG_UI_PKG.read_text())
    assert pkg["version"] == "0.0.47", (
        f"AG-UI core version drifted: {pkg['version']} (expected 0.0.47). "
        "Update mapper docstring + this canary together.")


def test_copilotkitnext_react_version_exact_pin() -> None:
    _skip_if_missing(CK_PKG)
    pkg = json.loads(CK_PKG.read_text())
    assert pkg["version"] == "1.53.0", (
        f"CopilotKit v2 react version drifted: {pkg['version']}. "
        "Verify dispatcher source still uses the four-step matcher.")


def test_dispatcher_predicate_unchanged() -> None:
    """Pin the four-step matcher logic in use-render-activity-message.mjs."""
    _skip_if_missing(DISPATCHER_MJS)
    src = DISPATCHER_MJS.read_text()
    assert "renderer.activityType === activityType" in src
    # agentId-bound exact → unbound exact → wildcard → null
    assert "candidate.agentId === agentId" in src
    assert "candidate.agentId === void 0" in src
    assert 'candidate.activityType === "*"' in src


def test_package_json_pins_are_exact() -> None:
    """Versions must NOT carry ^ or ~ for AG-UI / CopilotKit deps."""
    pkg = json.loads(PACKAGE_JSON.read_text())
    deps = {**pkg.get("dependencies", {}),
            **pkg.get("devDependencies", {})}
    for name in ("@ag-ui/core", "@ag-ui/client",
                  "@copilotkit/react-core", "@copilotkit/react-ui",
                  "@copilotkitnext/react"):
        if name not in deps:
            continue
        v = deps[name]
        assert not v.startswith(("^", "~", ">", "<")), (
            f"{name} must be exact-pinned for the activity-message "
            f"dispatcher canary; got {v!r}")

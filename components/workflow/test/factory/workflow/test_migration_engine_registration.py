"""Companion-X Migration engine registration and enrollment authority tests."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from factory.mcp_utils.interface import service_binding, service_callers
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.workflow.mcp.execution import register
from factory.workflow.runtime.models import Settings


_LIVE_CONFIG = "projects/companion_x/config/settings.yaml"
_TEMPLATE_CONFIG = "projects/companion_x/config/settings.yaml.example"


def _engine_ids(settings: Settings) -> set[str]:
    return {item.engine_id for item in settings.execution_engines.engines}


def _load_settings() -> dict:
    """Load the pinned deployment contract.

    The live ``settings.yaml`` is untracked machine state (``projects/*/config/``
    is gitignored, issue #34), so a fresh clone has none; the tracked
    ``.example`` template is the reviewed contract a checkout can guarantee.
    When a live file exists it must parse *and* still register every engine the
    template registers — a deployment whose file silently dropped a
    registration is exactly how the reconstructed config lost
    ``migration_import`` and failed later as ``unknown execution engine``
    (#34, #57 item 5).
    """
    root = Path(__file__).parents[5]
    template = root / _TEMPLATE_CONFIG
    assert template.exists(), (
        f"tracked deployment template {_TEMPLATE_CONFIG} is missing; the pinned "
        "execution-engine registration contract lives there (issue #34)"
    )
    raw = yaml.safe_load(template.read_text())
    live = root / _LIVE_CONFIG
    if live.exists():
        live_settings = Settings.model_validate(yaml.safe_load(live.read_text()))
        missing = _engine_ids(Settings.model_validate(raw)) - _engine_ids(live_settings)
        assert not missing, (
            f"the machine-local {_LIVE_CONFIG} does not register {sorted(missing)}, "
            f"which the tracked template does: a deployment that drops an engine "
            "registration fails later as 'unknown execution engine: <id>' (#57)"
        )
    return raw


def test_companion_x_registers_bounded_migration_engine() -> None:
    raw = _load_settings()
    settings = Settings.model_validate(raw)
    engines = {item.engine_id: item for item in settings.execution_engines.engines}
    migration = engines["migration_import"]
    assert migration.invoke_target.brick_name == "migration"
    assert migration.invoke_target.tool_name == "migration_apply_execution"
    assert migration.max_attempts == 3
    assert migration.max_continuations == 1000
    assert migration.outcome.success.model_dump() == {
        "pointer": "/status", "equals": "completed"}
    assert migration.outcome.continuation.model_dump() == {
        "pointer": "/status", "equals": "partial"}
    assert migration.outcome.retryable.model_dump() == {
        "pointer": "/retryable", "equals": True}


def test_only_agent_and_migration_may_enroll_execution() -> None:
    catalog = ToolCatalog("workflow")
    register(catalog, MagicMock())
    tools = {tool.name: tool for tool in asyncio.run(catalog.list_tools())}
    enroll = tools["workflow.enroll_execution"]
    append = tools["workflow.append_execution_event"]
    assert service_callers(enroll) == frozenset({"agent", "migration"})
    assert service_binding(enroll) == "enrollment"
    assert service_callers(append) == frozenset({"agent"})
    assert service_binding(append) == "execution"

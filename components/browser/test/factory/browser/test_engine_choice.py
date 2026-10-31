"""Browser engine choice, readiness detection, and launch smoke."""
from __future__ import annotations

import asyncio

from factory.browser import server
from factory.browser.runtime.adapters.mock import MockAdapter
from factory.browser.runtime.runtime import BrowserRuntime


def _tools(runtime=None):
    catalog = server.create_tool_catalog(runtime)
    return {tool.name: tool for tool in asyncio.run(catalog.list_tools())}


def test_engine_is_selected_from_env_and_defaults_to_mock(monkeypatch) -> None:
    monkeypatch.delenv(server.ENGINE_ENV, raising=False)
    assert server.selected_engine() == "mock"
    assert server._runtime(None)._adapter.__class__.__name__ == "MockAdapter"
    monkeypatch.setenv(server.ENGINE_ENV, "CDP")
    assert server.selected_engine() == "cdp"
    assert server._runtime(None)._adapter.__class__.__name__ == "CDPAdapter"
    monkeypatch.setenv(server.ENGINE_ENV, "playwright")  # never existed; fail closed to mock
    assert server.selected_engine() == "mock"


def test_capabilities_no_longer_advertise_a_phantom_adapter() -> None:
    tools = _tools()
    caps = tools["browser.get_capabilities"].fn()
    assert caps.data.adapters == ["cdp", "mock"]
    assert server.get_capabilities()["adapters"] == ["mock", "cdp"]


def test_engine_status_is_pure_detection(monkeypatch) -> None:
    monkeypatch.setenv(server.ENGINE_ENV, "mock")
    status = _tools()["browser.get_engine_status"].fn().data
    assert status.engine == "mock" and status.available_engines == ["mock", "cdp"]
    assert status.chrome_found == (status.chrome_path is not None)
    assert isinstance(status.websockets_available, bool)
    assert server.ENGINE_ENV in status.change_hint


def test_engine_smoke_reports_success_and_failure_truthfully(monkeypatch) -> None:
    monkeypatch.setenv(server.ENGINE_ENV, "mock")
    ok = asyncio.run(_tools(BrowserRuntime(MockAdapter()))["browser.engine_smoke"].fn()).data
    assert ok.ok is True and ok.browser_type == "mock" and ok.elapsed_ms >= 0

    class Broken(MockAdapter):
        async def launch(self, config):  # type: ignore[override]
            raise RuntimeError("chromium: command not found")

    bad = asyncio.run(_tools(BrowserRuntime(Broken()))["browser.engine_smoke"].fn()).data
    assert bad.ok is False and "command not found" in (bad.error or "")


def test_health_check_reflects_the_selected_engine_not_a_hardcoded_mock(monkeypatch) -> None:
    monkeypatch.setenv(server.ENGINE_ENV, "mock")
    assert server.health_check()["adapter"] == "mock"
    monkeypatch.setenv(server.ENGINE_ENV, "cdp")
    assert server.health_check()["adapter"] == "cdp"

"""Focused native-v2 mode and public-admission parity canaries."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_meta import META_TOOL_NAMES
from factory.mcp_server.runtime.native_v2_bootstrap import build_configured_native_server
from factory.mcp_server.runtime.public_admission import project_public_tools
from factory.mcp_server.runtime.tool_catalog import build_tool_catalog
from factory.mcp_utils.interface import ToolResult, ok, operational, service_only
from factory.mcp_utils.runtime.tool_catalog import CatalogTool, ToolCatalog


class InputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: int = 1


class OutputDTO(BaseModel):
    value: int


def _typed(value: int = 1) -> ToolResult[OutputDTO]:
    return ok(OutputDTO(value=value))


def _catalog(*, untyped: bool = False, service: bool = False) -> ToolCatalog:
    catalog = ToolCatalog("demo")
    handler = operational(
        input_model=InputDTO, output_model=OutputDTO,
    )(_typed)
    if service:
        handler = service_only(callers={"workflow"}, binding="attempt")(handler)
    catalog.add_tool(CatalogTool("demo_tool", "", handler))
    if untyped:
        catalog.add_tool(CatalogTool("demo_bad", "", lambda: {}))
    return catalog


def _aggregator(catalog: ToolCatalog) -> MCPAggregator:
    aggregator = MCPAggregator()
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = catalog
    return aggregator


class _Composer:
    last: "_Composer | None" = None

    def __init__(self, plan: Any, registrations: tuple[Any, ...]) -> None:
        self.plan, self.registrations = plan, registrations
        _Composer.last = self

    def compose(self) -> "_Composer":
        return self


def _patch_composer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "factory.mcp_server.runtime.native_v2_bootstrap.NativeMCPV2Composer",
        _Composer,
    )


def test_progressive_registers_exact_meta_without_loading_bricks(monkeypatch) -> None:
    _patch_composer(monkeypatch)
    aggregator = _aggregator(_catalog())
    monkeypatch.setattr(
        aggregator._lazy, "ensure_loaded",
        lambda _name: (_ for _ in ()).throw(AssertionError("eager load")),
    )
    _, plan = build_configured_native_server(
        aggregator, server_name="test", discovery_mode="progressive",
    )
    assert plan.discovery_mode == "progressive"
    assert plan.selected_tools == META_TOOL_NAMES


def test_flat_without_allowlist_registers_only_admitted_public(monkeypatch) -> None:
    _patch_composer(monkeypatch)
    _, plan = build_configured_native_server(
        _aggregator(_catalog()), server_name="test", discovery_mode="flat",
    )
    assert plan.discovery_mode == "flat"
    assert plan.selected_tools == {"demo_tool"}


def test_flat_empty_allowlist_registers_zero_tools(monkeypatch) -> None:
    _patch_composer(monkeypatch)
    _, plan = build_configured_native_server(
        _aggregator(_catalog()), server_name="test", discovery_mode="flat",
        allowlist=set(),
    )
    assert plan.selected_tools == set()


def test_flat_single_allowlist_registers_exactly_one_tool(monkeypatch) -> None:
    _patch_composer(monkeypatch)
    _, plan = build_configured_native_server(
        _aggregator(_catalog()), server_name="test", discovery_mode="flat",
        allowlist={"demo_tool"},
    )
    assert plan.selected_tools == {"demo_tool"}


def test_flat_fails_closed_for_invalid_selected_public(monkeypatch) -> None:
    _patch_composer(monkeypatch)
    with pytest.raises(ValueError, match="input_model_not_concrete"):
        build_configured_native_server(
            _aggregator(_catalog(untyped=True)), server_name="test",
            discovery_mode="flat", allowlist={"demo_bad"},
        )


def test_service_only_is_never_public_even_when_explicitly_selected(monkeypatch) -> None:
    _patch_composer(monkeypatch)
    aggregator = _aggregator(_catalog(service=True))
    _, plan = build_configured_native_server(
        aggregator, server_name="test", discovery_mode="flat",
        allowlist={"demo_tool"},
    )
    assert plan.selected_tools == set()


def test_catalog_and_discovery_share_admission_and_safe_diagnostics() -> None:
    aggregator = _aggregator(_catalog(untyped=True))
    discovered = aggregator.get_brick_tools("demo")
    complete = build_tool_catalog(aggregator)
    assert [item["name"] for item in discovered["tools"]] == ["demo_tool"]
    assert [item["qualified_name"] for item in complete["tools"]] == ["demo_tool"]
    expected = [{
        "brick": "demo", "source_name": "demo_bad",
        "public_name": "demo_bad", "reason": "input_model_not_concrete",
    }]
    assert discovered["invalid_tools"] == expected
    assert complete["invalid_tools"] == expected


def test_distinct_handlers_with_same_canonical_name_are_invalid() -> None:
    first = operational(input_model=InputDTO, output_model=OutputDTO)(_typed)
    second = operational(input_model=InputDTO, output_model=OutputDTO)(
        lambda value=1: ok(OutputDTO(value=value)),
    )
    projection = project_public_tools((("demo", {
        "demo.echo": CatalogTool("demo.echo", "", first),
        "demo_echo": CatalogTool("demo_echo", "", second),
    }),))
    assert projection.admitted == ()
    assert {item["reason"] for item in projection.invalid_tools} == {
        "canonical_name_collision",
    }


@pytest.mark.asyncio
async def test_dispatch_unexpected_failure_never_exposes_exception_details() -> None:
    from factory.mcp_server.runtime.tool_dispatch import invoke_catalog_tool

    secret = "dispatch-secret-canary"

    def explode() -> None:
        raise RuntimeError(secret)

    result = await invoke_catalog_tool(
        CatalogTool("demo_explode", "", explode), "demo", "demo_explode", {},
    )
    assert result == {
        "ok": False,
        "error": {"type": "ToolExecutionError", "message": "tool_execution_failed"},
    }
    assert secret not in repr(result)

"""The surviving generic API routes never expose or authorize service-only tools.

bd:python-factory-736 retired ``/api/tools``, ``/api/tools/resolve/{partial}``,
``/api/tools/catalog``, and ``POST /api/tools/{tool_name}`` — the routes this
test used to exercise the service-only boundary through. Real MCP's
``get_tool_catalog``/``call_brick_tool`` meta-tools already have their own
dedicated service-only coverage (``bases/mcp_server/test/.../
test_service_only_boundary.py::test_protected_tool_is_absent_from_every_public_server_surface``),
so this file now only proves the two REST routes that DO survive
(``/api/health``, ``/api/personas``) never leak a service-only tool's
existence or invoke it — e.g. via ``get_aggregated_capabilities``'s
``total_tools`` count or ``get_all_tool_names``.
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from factory.mcp_utils.interface import ToolCatalog
from pydantic import BaseModel, ConfigDict

from factory.api.runtime.bridge import register_bridge_routes
from factory.mcp_server.interface import MCPAggregator
from factory.mcp_utils.interface import ToolResult, ok, operational, service_only


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    workflow_run_id: str
    attempt_id: str
    revision: int
    manifest_digest: str


class _Output(BaseModel):
    changed: bool


class _PublicInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _PublicOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    public: bool


def _client():
    effects: list[str] = []
    child = ToolCatalog("demo")

    @child.tool(name="demo_public")
    @operational(input_model=_PublicInput, output_model=_PublicOutput)
    def public() -> ToolResult[_PublicOutput]:
        return ok(_PublicOutput(public=True))

    @child.tool(name="demo_protected")
    @service_only(callers={"workflow"}, binding="attempt")
    @operational(input_model=_Input, output_model=_Output)
    def protected(
        workflow_run_id: str, attempt_id: str, revision: int,
        manifest_digest: str,
    ) -> ToolResult[_Output]:
        effects.append(workflow_run_id)
        return ok(_Output(changed=True))

    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = child
    app = FastAPI()
    with patch("factory.api.runtime.bridge._get_aggregator", return_value=aggregator):
        register_bridge_routes(app)
    return TestClient(app), aggregator, effects


def test_health_route_tool_count_excludes_service_only_tools() -> None:
    client, aggregator, effects = _client()
    with patch("factory.api.runtime.bridge._get_aggregator", return_value=aggregator), \
         patch("factory.api.runtime.views.ensure_views_registered"):
        health = client.get("/api/health").json()

    # get_all_tool_names() (used for total_tools) is public-only.
    assert health["total_tools"] == 1
    assert effects == []


def test_personas_route_never_invokes_a_service_only_tool() -> None:
    """Not the service-only tool itself, but proves the route only ever
    calls the one fixed public tool it is wired to — it cannot be coerced
    into invoking anything else, service-only or not."""
    client, aggregator, effects = _client()
    with patch("factory.api.runtime.bridge._get_aggregator", return_value=aggregator):
        resp = client.get("/api/personas")
    assert resp.status_code == 200
    # agent_get_agent_registry doesn't exist on this fixture aggregator,
    # so invoke_tool fails closed to an empty list rather than falling
    # through to any other tool name.
    assert resp.json() == {"personas": [], "count": 0}
    assert effects == []

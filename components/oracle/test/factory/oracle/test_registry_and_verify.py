"""Registry overlay + end-to-end verify dispatch (bd python-factory-216ti)."""

from __future__ import annotations

from typing import Any

import pytest

from factory.graph.mcp.core_models import EntityData, EntityLookupData, FindingStateData
from factory.mcp_utils.interface import get_service, set_service
from factory.mcp_utils.runtime.tool_result import ToolResult, ok
from factory.mcp_utils.tools import get_tool_map
from factory.oracle.interface import create_server, get_registry, reset_registry
from factory.oracle.runtime.registry import VerifierRegistry


class _StubVerifier:
    def __init__(self, name: str, state: str) -> None:
        self.name = name
        self._state = state

    def verify(self, finding: dict[str, Any], context: dict[str, Any]) -> dict:
        return {"state": self._state, "evidence": "stub", "verifier": self.name}


class TestRegistryOverlay:
    def test_builtin_wins_on_collision(self) -> None:
        reg = VerifierRegistry()
        reg.register_builtin("d", _StubVerifier("builtin", "verified"))
        reg.register("d", _StubVerifier("pack", "refuted"))
        assert reg.resolve("d").name == "builtin"

    def test_pack_overlay_registers(self) -> None:
        reg = VerifierRegistry()
        reg.register("wine", _StubVerifier("wine", "verified"))
        assert reg.resolve("wine").name == "wine"
        assert reg.resolve("") is None
        assert "wine" in reg.domains()


class TestVerifyFindingTool:
    """Verification remains graph-name-indirected under the typed envelope."""

    def setup_method(self) -> None:
        reset_registry()
        self._prev = get_service("tool_invoker")
        self._calls: list[tuple] = []
        self._state_store = {"f-1": "candidate"}

        def _invoker(tool_name: str, **kwargs: Any) -> ToolResult[Any] | dict[str, Any]:
            self._calls.append((tool_name, kwargs))
            if tool_name == "graph_graph_get_entity":
                fid = kwargs["entity_id"]
                if fid not in self._state_store:
                    return ok(EntityLookupData(found=False, entity_id=fid))
                return ok(EntityLookupData(
                    found=True, entity_id=fid,
                    entity=EntityData(id=fid, type="Finding", properties={
                        "id": fid, "state": self._state_store[fid],
                        "location": "http://app/x",
                    }),
                ))
            if tool_name == "graph_graph_set_finding_state":
                self._state_store[kwargs["finding_id"]] = kwargs["state"]
                return ok(FindingStateData(
                    success=True, finding_id=kwargs["finding_id"], state=kwargs["state"],
                ))
            if tool_name == "security_security_pentest_scan":
                return {"status": "vulnerable", "findings": [{"id": "v1"}]}
            raise AssertionError(f"unexpected tool {tool_name}")

        set_service("tool_invoker", _invoker)
        self._tools = get_tool_map(create_server())

    def teardown_method(self) -> None:
        set_service("tool_invoker", self._prev)
        reset_registry()

    def _verify(self, **kw: Any) -> ToolResult[Any]:
        return self._tools["oracle_verify_finding"](**kw)

    def test_unknown_finding_is_successful_typed_negative_data(self) -> None:
        result = self._verify(finding_id="ghost")
        assert result.ok and result.data.success is False
        assert result.data.persisted is False
        assert "not found" in result.data.error

    def test_generic_fallback_persists_unchanged_state(self) -> None:
        result = self._verify(finding_id="f-1")
        assert result.ok and result.data.state == "candidate"
        assert result.data.verifier == "generic-fallback"
        assert self._state_store["f-1"] == "candidate"

    def test_security_pack_verifier_drives_verified(self) -> None:
        from factory.security.runtime.adapters.oracle_verifier import register_security_verifier

        assert register_security_verifier() is True
        result = self._verify(finding_id="f-1", domain="security")
        assert result.ok and result.data.state == "verified"
        assert result.data.verifier == "security-pentest"
        assert result.data.persisted is True
        assert self._state_store["f-1"] == "verified"
        assert any(call[0] == "security_security_pentest_scan" for call in self._calls)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

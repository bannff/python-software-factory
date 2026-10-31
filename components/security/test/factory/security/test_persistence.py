"""Tests for finding persistence adapters (memory + graph) and runtime integration."""
from __future__ import annotations
from typing import Any
from unittest.mock import MagicMock, patch
import pytest
from factory.security.runtime.adapters.memory_persistence import MemoryFindingPersistence
from factory.security.runtime.adapters.graph_persistence import GraphFindingPersistence
from factory.security.runtime.adapters.mock import MockAnalyzerAdapter
from factory.security.runtime.runtime import SecurityRuntime
from factory.security.core import AnalysisType
FINDINGS: list[dict[str, Any]] = [
    {"id": "f1", "severity": "high", "title": "SQL Injection", "description": "Unsanitized"},
    {"id": "f2", "severity": "low", "title": "Debug flag", "description": "Debug enabled"},
]
_INVOKE = "factory.security.runtime.adapters.graph_persistence._invoke"

class TestMemoryPersistence:
    @pytest.fixture
    def s(self) -> MemoryFindingPersistence:
        return MemoryFindingPersistence()

    def test_persist_and_retrieve(self, s: MemoryFindingPersistence) -> None:
        """Stores data retrievable by get_analysis."""
        res = s.persist_analysis("a1", "code_analysis", "/src", FINDINGS, "ok")
        assert res["persisted"] is True and res["backend"] == "memory" and res["finding_count"] == 2
        got = s.get_analysis("a1")
        assert got is not None and got["analysis_id"] == "a1" and len(got["findings"]) == 2

    def test_get_analysis_missing(self, s: MemoryFindingPersistence) -> None:
        assert s.get_analysis("nope") is None

    def test_list_analyses(self, s: MemoryFindingPersistence) -> None:
        """Returns all stored; respects limit."""
        assert s.list_analyses() == []
        s.persist_analysis("a1", "scan", "/a", [], None)
        s.persist_analysis("a2", "recon", "/b", FINDINGS, None)
        assert len(s.list_analyses()) == 2
        for i in range(10):
            s.persist_analysis(f"x{i}", "s", "/x", [], None)
        assert len(s.list_analyses(limit=3)) == 3

    def test_get_findings_all(self, s: MemoryFindingPersistence) -> None:
        """Returns findings across analyses with analysis_id attached."""
        s.persist_analysis("a1", "scan", "/x", FINDINGS, None)
        assert len(s.get_findings()) == 2
        assert all("analysis_id" in f for f in s.get_findings())

    def test_get_findings_filter_severity(self, s: MemoryFindingPersistence) -> None:
        s.persist_analysis("a1", "scan", "/x", FINDINGS, None)
        assert len(s.get_findings(severity="high")) == 1
        assert s.get_findings(severity="critical") == []

    def test_get_findings_limit(self, s: MemoryFindingPersistence) -> None:
        many = [{"id": f"f{i}", "severity": "low", "title": "t"} for i in range(20)]
        s.persist_analysis("a1", "scan", "/x", many, None)
        assert len(s.get_findings(limit=5)) == 5

    def test_health_check(self, s: MemoryFindingPersistence) -> None:
        assert s.health_check() == {"healthy": True, "backend": "memory", "count": 0}
        s.persist_analysis("a1", "scan", "/x", [], None)
        assert s.health_check()["count"] == 1


class TestGraphPersistence:
    @pytest.fixture
    def agg(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def s(self, agg: MagicMock) -> GraphFindingPersistence:
        with patch("factory.security.runtime.adapters.graph_persistence._get_aggregator", return_value=agg):
            yield GraphFindingPersistence()

    def _pi(self, agg: MagicMock) -> Any:
        return patch(_INVOKE, side_effect=lambda tool, **kw: agg.invoke_tool(tool, **kw))

    def test_persist_creates_nodes_and_edges(self, s: GraphFindingPersistence, agg: MagicMock) -> None:
        with self._pi(agg):
            res = s.persist_analysis("a1", "code_analysis", "/src", FINDINGS, "ok")
        assert res["persisted"] is True and res["findings_persisted"] == 2
        calls = [c[0][0] for c in agg.invoke_tool.call_args_list]
        assert calls.count("graph_graph_add_entity") == 3
        assert calls.count("graph_graph_add_relationship") == 2

    def test_persist_handles_action_error(self, s: GraphFindingPersistence) -> None:
        with patch(_INVOKE, side_effect=RuntimeError("graph down")):
            res = s.persist_analysis("a1", "scan", "/x", FINDINGS)
        assert res["persisted"] is False and "error" in res

    def test_persist_partial_finding_failure(self, s: GraphFindingPersistence) -> None:
        n = {"count": 0}
        def _se(tool: str, **kw: Any) -> Any:
            n["count"] += 1
            if n["count"] == 1:
                return MagicMock(ok=True, data=object())
            if n["count"] == 2:
                raise RuntimeError("boom")
            return MagicMock(ok=True, data=object())
        with patch(_INVOKE, side_effect=_se):
            res = s.persist_analysis("a1", "scan", "/x", FINDINGS)
        assert res["persisted"] is False
        assert res["findings_persisted"] < res["findings_total"]

    def test_get_analysis_found(self, s: GraphFindingPersistence, agg: MagicMock) -> None:
        agg.invoke_tool.side_effect = [
            MagicMock(ok=True, data=MagicMock(
                found=True, entity=MagicMock(properties={"action_type": "scan"}),
            )),
            MagicMock(ok=True, data=MagicMock(
                neighbors=[MagicMock(properties={"severity": "high"})],
            )),
        ]
        with self._pi(agg):
            res = s.get_analysis("a1")
        assert res is not None and res["analysis_id"] == "a1" and len(res["findings"]) == 1

    def test_get_analysis_not_found(self, s: GraphFindingPersistence, agg: MagicMock) -> None:
        agg.invoke_tool.return_value = MagicMock(
            ok=True, data=MagicMock(found=False, entity=None),
        )
        with self._pi(agg):
            assert s.get_analysis("missing") is None

    def test_list_analyses(self, s: GraphFindingPersistence, agg: MagicMock) -> None:
        agg.invoke_tool.return_value = MagicMock(ok=True, data=MagicMock(
            entities=[MagicMock(id="action-a1", properties={"action_type": "scan"})],
        ))
        with self._pi(agg):
            res = s.list_analyses()
        assert len(res) == 1 and res[0]["analysis_id"] == "a1"

    def test_get_findings_with_severity(self, s: GraphFindingPersistence, agg: MagicMock) -> None:
        """Surfaces taxonomy badges from the typed-tool result."""
        agg.invoke_tool.return_value = MagicMock(ok=True, data=MagicMock(rows=[
            {"id": "f1", "severity": "high", "title": "XSS",
             "cwe_name": "XSS", "cwe_id": "CWE-79",
             "ocsf_class": "Security Finding", "ocsf_uid": 2001},
        ]))
        with self._pi(agg):
            res = s.get_findings(severity="high")
        assert len(res) == 1
        assert res[0]["cwe_id"] == "CWE-79"
        assert res[0]["ocsf_class"] == "Security Finding"
        assert agg.invoke_tool.call_args[0][0] == "graph_graph_get_recent_findings"

    def test_get_findings_no_severity(self, s: GraphFindingPersistence, agg: MagicMock) -> None:
        """severity=None is passed as empty string to the typed tool."""
        agg.invoke_tool.return_value = MagicMock(ok=True, data=MagicMock(rows=[
            {"id": "f1", "severity": "low", "title": "info"},
        ]))
        with self._pi(agg):
            res = s.get_findings()
        assert len(res) == 1 and "cwe_id" not in res[0]
        assert agg.invoke_tool.call_args[1]["severity"] == ""

    def test_health_check_healthy(self, s: GraphFindingPersistence, agg: MagicMock) -> None:
        agg.invoke_tool.return_value = MagicMock(
            ok=True,
            data=MagicMock(healthy=True, graphs={"default": MagicMock(nodes=42)}),
        )
        with self._pi(agg):
            res = s.health_check()
        assert res == {"healthy": True, "backend": "graph", "graph_nodes": 42}

    def test_health_check_error(self, s: GraphFindingPersistence) -> None:
        with patch(_INVOKE, side_effect=RuntimeError("unreachable")):
            res = s.health_check()
        assert res["healthy"] is False and "error" in res


class TestRuntimePersistenceIntegration:
    @pytest.fixture
    def mp(self) -> MagicMock:
        p = MagicMock()
        p.persist_analysis.return_value = {"persisted": True}
        p.get_findings.return_value = [{"id": "f1"}]
        p.list_analyses.return_value = [{"analysis_id": "a1"}]
        p.health_check.return_value = {"healthy": True, "backend": "mock"}
        return p

    @pytest.fixture
    def rt(self, mp: MagicMock) -> SecurityRuntime:
        return SecurityRuntime(MockAnalyzerAdapter(), persistence=mp)

    @pytest.mark.asyncio
    async def test_analyze_calls_persist(self, rt: SecurityRuntime, mp: MagicMock) -> None:
        await rt.analyze("target", AnalysisType.CODE_ANALYSIS)
        mp.persist_analysis.assert_called_once()
        kw = mp.persist_analysis.call_args[1]
        assert kw["target"] == "target" and kw["analysis_type"] == "code_analysis"

    def test_get_persisted_findings(self, rt: SecurityRuntime, mp: MagicMock) -> None:
        assert rt.get_persisted_findings(severity="high", limit=10) == [{"id": "f1"}]
        mp.get_findings.assert_called_once_with(severity="high", limit=10)

    def test_list_persisted_analyses(self, rt: SecurityRuntime, mp: MagicMock) -> None:
        assert rt.list_persisted_analyses(limit=5) == [{"analysis_id": "a1"}]
        mp.list_analyses.assert_called_once_with(limit=5)

    def test_persistence_health(self, rt: SecurityRuntime, mp: MagicMock) -> None:
        assert rt.persistence_health()["healthy"] is True
        mp.health_check.assert_called_once()

    def test_default_persistence_is_memory(self) -> None:
        assert SecurityRuntime(MockAnalyzerAdapter()).persistence_health()["backend"] == "memory"

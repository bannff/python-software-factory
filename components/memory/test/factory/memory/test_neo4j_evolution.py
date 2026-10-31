"""Tests for neo4j_evolution.py — A-MEM evolution helpers.

Covers: run_content_analysis, set_evolution_properties, evolve,
_find_neighbors, _apply_evolution_result, and error handling.
All Neo4j interactions are mocked — no running instance required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from factory.memory.runtime.evolution import EvolutionResult, NeighborInfo
from factory.memory.runtime.adapters.neo4j_evolution import (
    _apply_evolution_result,
    _find_neighbors,
    evolve,
    run_content_analysis,
    set_evolution_properties,
)


def _mock_driver():
    """Return a mock Neo4j driver with session context manager."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver, session


def _make_memory(mid: str = "mem-1") -> MagicMock:
    m = MagicMock()
    m.id = mid
    return m


class TestRunContentAnalysis:
    def test_delegates_to_analyze_content(self) -> None:
        with patch("factory.memory.runtime.adapters.neo4j_evolution.analyze_content") as mock_ac:
            mock_ac.return_value = {"keywords": ["k"], "context": "ctx", "tags": ["t"]}
            result = run_content_analysis(MagicMock(), "some content")
            mock_ac.assert_called_once()
            assert result["keywords"] == ["k"]

    def test_passes_llm_and_content_through(self) -> None:
        llm = MagicMock()
        with patch("factory.memory.runtime.adapters.neo4j_evolution.analyze_content") as mock_ac:
            mock_ac.return_value = {}
            run_content_analysis(llm, "text")
            mock_ac.assert_called_once_with(llm, "text")


class TestSetEvolutionProperties:
    def test_sets_keywords_context_tags(self) -> None:
        driver, session = _mock_driver()
        analysis = {"keywords": ["ai"], "context": "About AI", "tags": ["tech"]}
        set_evolution_properties(driver, "testdb", "mem-1", analysis)
        _, kwargs = session.run.call_args
        assert kwargs["mid"] == "mem-1"
        assert kwargs["keywords"] == ["ai"]
        assert kwargs["context"] == "About AI"

    def test_defaults_for_missing_keys(self) -> None:
        driver, session = _mock_driver()
        set_evolution_properties(driver, "testdb", "mem-1", {})
        _, kwargs = session.run.call_args
        assert kwargs["keywords"] == []
        assert kwargs["context"] == "General"
        assert kwargs["tags"] == []


class TestFindNeighbors:
    def test_returns_neighbor_info_from_cypher(self) -> None:
        driver, session = _mock_driver()
        session.run.return_value = [
            {"id": "n1", "content": "c1", "context": "ctx1", "keywords": ["k"], "tags": ["t"]},
        ]
        vec_fn = MagicMock(return_value=[_make_memory("n1")])
        result = _find_neighbors(driver, "db", "user1", vec_fn)
        assert len(result) == 1
        assert isinstance(result[0], NeighborInfo)
        assert result[0].memory_id == "n1"

    def test_empty_when_vector_search_returns_nothing(self) -> None:
        driver, _ = _mock_driver()
        assert _find_neighbors(driver, "db", "u", MagicMock(return_value=[])) == []

    def test_limits_to_five_ids(self) -> None:
        driver, session = _mock_driver()
        session.run.return_value = []
        vec_fn = MagicMock(return_value=[_make_memory(f"m{i}") for i in range(10)])
        _find_neighbors(driver, "db", "u", vec_fn)
        _, kwargs = session.run.call_args
        assert len(kwargs["ids"]) == 5

    def test_handles_null_properties(self) -> None:
        driver, session = _mock_driver()
        session.run.return_value = [
            {"id": "n1", "content": None, "context": None, "keywords": None, "tags": None},
        ]
        result = _find_neighbors(driver, "db", "u", MagicMock(return_value=[_make_memory("n1")]))
        assert result[0].content == ""
        assert result[0].keywords == []


class TestEvolve:
    def test_with_neighbors_calls_engine(self) -> None:
        driver, session = _mock_driver()
        engine = MagicMock()
        engine.analyze.return_value = EvolutionResult(
            should_evolve=True, connections=["n1"], neighbor_updates=[],
        )
        session.run.return_value = [
            {"id": "n1", "content": "c", "context": "x", "keywords": [], "tags": []},
        ]
        evolve(engine, driver, "db", "mem-1", "u", "content", {}, MagicMock(return_value=[_make_memory("n1")]))
        engine.analyze.assert_called_once()

    def test_no_neighbors_skips_analysis(self) -> None:
        driver, _ = _mock_driver()
        engine = MagicMock()
        evolve(engine, driver, "db", "mem-1", "u", "content", {}, MagicMock(return_value=[]))
        engine.analyze.assert_not_called()

    def test_should_evolve_false_skips_apply(self) -> None:
        driver, session = _mock_driver()
        engine = MagicMock()
        engine.analyze.return_value = EvolutionResult(should_evolve=False)
        session.run.return_value = [
            {"id": "n1", "content": "c", "context": "x", "keywords": [], "tags": []},
        ]
        with patch("factory.memory.runtime.adapters.neo4j_evolution._apply_evolution_result") as mock_apply:
            evolve(engine, driver, "db", "mem-1", "u", "c", {}, MagicMock(return_value=[_make_memory("n1")]))
            mock_apply.assert_not_called()

    def test_handles_exception_gracefully(self) -> None:
        driver, _ = _mock_driver()
        vec_fn = MagicMock(side_effect=RuntimeError("boom"))
        evolve(MagicMock(), driver, "db", "mem-1", "u", "c", {}, vec_fn)


class TestApplyEvolutionResult:
    def test_creates_related_to_edges(self) -> None:
        driver, session = _mock_driver()
        result = EvolutionResult(should_evolve=True, connections=["n1", "n2"], neighbor_updates=[])
        _apply_evolution_result(driver, "db", result, "mem-1")
        related = [c for c in session.run.call_args_list if "RELATED_TO" in str(c)]
        assert len(related) == 2

    def test_updates_neighbor_and_creates_evolved_from(self) -> None:
        driver, session = _mock_driver()
        result = EvolutionResult(
            should_evolve=True, connections=[],
            neighbor_updates=[{"memory_id": "n1", "context": "new ctx", "tags": ["t1"]}],
        )
        _apply_evolution_result(driver, "db", result, "mem-1")
        evolved = [c for c in session.run.call_args_list if "EVOLVED_FROM" in str(c)]
        assert len(evolved) == 1
        set_calls = [c for c in session.run.call_args_list if "SET" in str(c) and "EVOLVED" not in str(c)]
        assert len(set_calls) >= 1

    def test_empty_result_no_mutations(self) -> None:
        driver, session = _mock_driver()
        _apply_evolution_result(driver, "db", EvolutionResult(should_evolve=True), "mem-1")
        session.run.assert_not_called()

    def test_partial_update_context_only(self) -> None:
        driver, session = _mock_driver()
        result = EvolutionResult(
            should_evolve=True, connections=[],
            neighbor_updates=[{"memory_id": "n1", "context": "new"}],
        )
        _apply_evolution_result(driver, "db", result, "mem-1")
        set_call = [c for c in session.run.call_args_list if "context" in str(c) and "EVOLVED" not in str(c)]
        assert len(set_call) == 1

"""MCP contract coverage for the deterministic JUnit comparator."""

from __future__ import annotations

import asyncio

from factory.test.interface import TestRuntime, create_server
from factory.test.runtime.junit_fixtures import case, write_report


def test_compare_junit_tool_is_registered_and_returns_contract(tmp_path) -> None:
    mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))
    base = write_report(tmp_path / "base.xml", case("test_debt", "failure"))
    candidate = write_report(tmp_path / "candidate.xml", case("test_debt"))
    tool = asyncio.run(mcp.get_tool("test_compare_junit"))
    result = tool.fn(base_report="base.xml", candidate_report="candidate.xml")
    assert result.ok is True
    assert result.data.resolved[0].reason == "executed_and_passed"
    assert result.data.blocking == []
    assert result.data.errors == []
    assert result.data.base.total == 1



def test_missing_junit_is_typed_blocking_without_parse_error(tmp_path) -> None:
    mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))
    write_report(tmp_path / "base.xml", case("test_debt", "failure"))
    result = asyncio.run(mcp.get_tool("test_compare_junit")).fn(
        base_report="base.xml", candidate_report="missing.xml"
    )
    data = result.data
    assert result.ok and data.passed is False
    assert data.errors == ["target_not_found"]
    assert data.parse_errors == 0
    assert data.blocking and data.regressions == len(data.blocking)
    assert data.base_report == "base.xml" and data.candidate_report == "missing.xml"
    assert data.resolved_count == 0 and data.unchanged == 0



def test_malformed_junit_is_typed_parse_error_with_blocking_entry(tmp_path) -> None:
    mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))
    (tmp_path / "base.xml").write_text("not xml", encoding="utf-8")
    write_report(tmp_path / "candidate.xml", case("test_ok"))
    result = asyncio.run(mcp.get_tool("test_compare_junit")).fn(
        base_report="base.xml", candidate_report="candidate.xml"
    )
    data = result.data
    assert result.ok and data.passed is False
    assert data.errors == ["invalid_report"] and data.parse_errors == 1
    assert data.blocking and data.regressions == len(data.blocking)
    assert data.base.total == 0 and data.candidate.total == 0



def test_junit_absolute_identity_is_root_relative_or_external_placeholder(tmp_path) -> None:
    mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))
    outside = tmp_path.parent / "outside.py"
    write_report(tmp_path / "base.xml", case("test_debt", "failure", file=str(outside)))
    write_report(tmp_path / "candidate.xml", case("test_debt", file=str(outside)))
    result = asyncio.run(mcp.get_tool("test_compare_junit")).fn(
        base_report="base.xml", candidate_report="candidate.xml"
    )
    assert result.ok
    identity = result.data.resolved[0].identity
    assert identity.startswith("<external-path>::")
    assert str(outside) not in str(result.data)

    inside = tmp_path / "inside.py"
    write_report(tmp_path / "base.xml", case("test_inside", "failure", file=str(inside)))
    write_report(tmp_path / "candidate.xml", case("test_inside", file=str(inside)))
    result = asyncio.run(mcp.get_tool("test_compare_junit")).fn(
        base_report="base.xml", candidate_report="candidate.xml"
    )
    assert result.data.resolved[0].identity.startswith("inside.py::")


def test_missing_reports_are_typed_blocking_results(tmp_path) -> None:
    mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))
    tool = asyncio.run(mcp.get_tool("test_compare_junit"))
    result = tool.fn(base_report="missing-base.xml", candidate_report="missing-candidate.xml")
    assert result.ok is True
    assert result.data.errors == ["target_not_found"]
    assert result.data.parse_errors == 0
    assert result.data.regressions == 1
    assert result.data.blocking[0].reason == "target_not_found"


def test_absolute_external_junit_identity_is_not_disclosed(tmp_path) -> None:
    from factory.test.runtime.mcp_projection import junit

    outside = tmp_path.parent / "private" / "secret.py"
    result = junit(
        tmp_path,
        tmp_path / "base.xml",
        tmp_path / "candidate.xml",
        {"passed": False, "blocking": [{
            "identity": f"{outside}::TestCase::test_secret",
            "phase": "execution", "baseline_outcome": "failure",
            "candidate_outcome": "failure", "reason": "new_debt",
        }]},
    )
    assert result["blocking"][0]["identity"] == "<external-path>::TestCase::test_secret"
    assert str(outside) not in str(result)


def test_directory_reports_are_rejected_as_invalid_reports(tmp_path) -> None:
    mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))
    (tmp_path / "base.xml").mkdir()
    write_report(tmp_path / "candidate.xml", case("test_ok"))
    result = asyncio.run(mcp.get_tool("test_compare_junit")).fn(
        base_report="base.xml", candidate_report="candidate.xml"
    )
    assert result.ok and result.data.passed is False
    assert result.data.errors == ["invalid_report"]
    assert result.data.parse_errors == 1


def test_junit_projection_bounds_entry_lists_and_preserves_counts(tmp_path) -> None:
    from factory.test.runtime.mcp_projection import junit

    entries = [{
        "identity": f"test_{index}", "phase": "call",
        "baseline_outcome": "failure", "candidate_outcome": "failure",
        "reason": "unchanged_debt",
    } for index in range(101)]
    projected = junit(
        tmp_path, tmp_path / "base.xml", tmp_path / "candidate.xml",
        {"passed": False, "blocking": entries},
    )
    assert len(projected["blocking"]) == 100
    assert projected["blocking_truncated"] is True
    assert projected["regressions"] == 101

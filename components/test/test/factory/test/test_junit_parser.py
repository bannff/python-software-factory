"""Focused validation tests for the stdlib JUnit parser."""

from __future__ import annotations

import subprocess
import sys

import pytest

from factory.test.interface import JUnitReportError, parse_junit_report
from factory.test.runtime.junit_fixtures import case, report, write_report


def test_tracks_all_outcomes_and_phases(tmp_path) -> None:
    path = tmp_path / "report.xml"
    write_report(
        path,
        case("test_pass[param]"),
        case("test_skip", "skipped"),
        case("test_xfail", "xfail"),
        case("test_failure", "failure"),
        case("test_setup", "error", phase="setup"),
        case("test_teardown", "error", phase="teardown"),
        case("test_collection", "error", phase="collection"),
    )
    parsed = parse_junit_report(path)
    assert [item.outcome for item in parsed.cases] == [
        "passed", "skipped", "xfail", "failure", "error", "error", "error"
    ]
    assert [item.phase for item in parsed.cases[-3:]] == ["setup", "teardown", "collection"]
    assert "test_pass[param]" in parsed.cases[0].identity


@pytest.mark.parametrize(
    "payload, message",
    [
        ("", "empty"),
        ("<testsuite>", "malformed"),
        (report(), "no testcases"),
        (report(case("test_a"), tests=2), "incomplete"),
        (report(case("test_a"), case("test_a")), "duplicate"),
        (report(case("test_a", "mystery")), "unknown"),
        (
            report(case("test_a")).replace("<testcase ", '<testcase status="mystery" '),
            "unknown testcase status",
        ),
        ("<!DOCTYPE x><testsuites />", "DTD/entity"),
    ],
)
def test_invalid_or_ambiguous_reports_fail_closed(tmp_path, payload, message) -> None:
    path = tmp_path / "bad.xml"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(JUnitReportError, match=message):
        parse_junit_report(path)


def test_missing_report_fails_closed(tmp_path) -> None:
    with pytest.raises(JUnitReportError, match="cannot read"):
        parse_junit_report(tmp_path / "missing.xml")


def test_utf16_dtd_is_rejected_before_entity_processing(tmp_path) -> None:
    path = tmp_path / "utf16.xml"
    path.write_bytes("<!DOCTYPE x><testsuites />".encode("utf-16"))
    with pytest.raises(JUnitReportError, match="DTD/entity"):
        parse_junit_report(path)


def test_report_byte_limit_is_enforced(tmp_path, monkeypatch) -> None:
    from factory.test.runtime import junit_parser

    monkeypatch.setattr(junit_parser, "_MAX_REPORT_BYTES", 32)
    path = tmp_path / "large.xml"
    path.write_bytes(b"<testsuites>" + b"x" * 40)
    with pytest.raises(JUnitReportError, match="byte limit"):
        parse_junit_report(path)


def test_xml_depth_and_text_limits_are_enforced(tmp_path, monkeypatch) -> None:
    from factory.test.runtime import junit_parser

    monkeypatch.setattr(junit_parser, "_MAX_XML_DEPTH", 3)
    deep = tmp_path / "deep.xml"
    deep.write_text("<testsuites><a><b><c /></b></a></testsuites>", encoding="utf-8")
    with pytest.raises(JUnitReportError, match="nesting depth"):
        parse_junit_report(deep)

    monkeypatch.setattr(junit_parser, "_MAX_XML_DEPTH", 64)
    monkeypatch.setattr(junit_parser, "_MAX_XML_TEXT_BYTES", 4)
    text = tmp_path / "text.xml"
    text.write_text("<testsuites><testsuite tests=\"0\" failures=\"0\" errors=\"0\" skipped=\"0\">"
                    "<system-out>12345</system-out></testsuite></testsuites>", encoding="utf-8")
    with pytest.raises(JUnitReportError, match="text exceeds"):
        parse_junit_report(text)


def test_testcase_limit_is_enforced(tmp_path, monkeypatch) -> None:
    from factory.test.runtime import junit_parser

    monkeypatch.setattr(junit_parser, "_MAX_TESTCASES", 1)
    path = tmp_path / "many.xml"
    write_report(path, case("test_one"), case("test_two"))
    with pytest.raises(JUnitReportError, match="testcase limit"):
        parse_junit_report(path)


def test_resource_limit_fails_before_full_tree_materialization(tmp_path, monkeypatch) -> None:
    from factory.test.runtime import junit_parser

    monkeypatch.setattr(junit_parser, "_MAX_XML_ELEMENTS", 1)
    monkeypatch.setattr(
        junit_parser.ET, "fromstring",
        lambda payload: pytest.fail("full tree must not be retained before limits are checked"),
    )
    path = tmp_path / "too-many-elements.xml"
    write_report(path, case("test_one"))
    with pytest.raises(JUnitReportError, match="element count"):
        parse_junit_report(path)


def test_phase_ignores_traceback_words_and_uses_structural_message(tmp_path) -> None:
    setup = case("test_setup", "error", phase="setup").replace(
        ">boom</error>", ">traceback called gc.collect()</error>",
    )
    call = case("test_call", "failure").replace(
        ">boom</failure>", ">collection helper failed</failure>",
    )
    collection = case("test_collection", "error", phase="collection")
    parsed = parse_junit_report(write_report(tmp_path / "phases.xml", setup, call, collection))
    assert [item.phase for item in parsed.cases] == ["setup", "call", "collection"]


def test_real_pytest_xunit1_collection_and_teardown_counters_parse(tmp_path) -> None:
    (tmp_path / "test_bad.py").write_text("import missing_junit_probe_dependency\n")
    (tmp_path / "test_phases.py").write_text(
        "import pytest\n"
        "@pytest.fixture\n"
        "def broken():\n    yield\n    raise RuntimeError('teardown')\n"
        "def test_fail(broken):\n    assert False\n",
    )
    output = tmp_path / "real.xml"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", str(tmp_path), "-q",
         "--continue-on-collection-errors", "-o", "junit_family=xunit1",
         f"--junitxml={output}"],
        capture_output=True, text=True,
    )
    assert completed.returncode == 1
    parsed = parse_junit_report(output)
    phases = [(item.name, item.phase) for item in parsed.cases]
    assert ("test_bad", "collection") in phases
    assert phases.count(("test_fail", "call")) == 1
    assert phases.count(("test_fail", "teardown")) == 1

"""Bounded, fail-closed stdlib parser for pytest JUnit XML reports."""
from __future__ import annotations

import io
import os
import stat
from pathlib import Path
from xml.etree import ElementTree as ET

from .junit_models import JUnitCase, JUnitReport

_ALLOWED_CASE_CHILDREN = {"error", "failure", "properties", "skipped", "system-err", "system-out"}
_COUNTERS = {"errors": "error", "failures": "failure", "skipped": "skipped"}
_MAX_REPORT_BYTES = 5 * 1024 * 1024
_MAX_XML_ELEMENTS = 100_000
_MAX_XML_DEPTH = 64
_MAX_XML_TEXT_BYTES = 64 * 1024
_MAX_XML_ATTRIBUTE_BYTES = 16 * 1024
_MAX_TESTCASES = 20_000
_MAX_IDENTITY_FIELD = 1_024

class JUnitReportError(ValueError):
    """Raised when a report cannot prove a complete, unambiguous run."""

def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]

def _integer(value: str | None, label: str) -> int:
    if value is None:
        raise JUnitReportError(f"missing testsuite {label!r} counter")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise JUnitReportError(f"invalid testsuite {label!r} counter: {value!r}") from exc
    if parsed < 0:
        raise JUnitReportError(f"negative testsuite {label!r} counter")
    return parsed

def _phase(element: ET.Element, outcome: str) -> str:
    """Classify pytest phases from its structural JUnit message only."""
    message = (element.get("message") or "").strip().lower()
    if message.startswith(("collection failure", "failed during collect")):
        return "collection"
    if message.startswith(("failed on teardown", "failed during teardown")):
        return "teardown"
    if message.startswith(("failed on setup", "failed during setup")):
        return "setup"
    return "call"

def _identity(element: ET.Element) -> tuple[str, str, str, str]:
    file_name = (element.get("file") or "").replace("\\", "/").removeprefix("./")
    classname = (element.get("classname") or "").strip()
    name = (element.get("name") or "").strip()
    if not name or not (file_name or classname):
        raise JUnitReportError("testcase identity requires name and file or classname")
    if any(len(value) > _MAX_IDENTITY_FIELD for value in (file_name, classname, name)):
        raise JUnitReportError("testcase identity exceeds resource limit")
    identity = "::".join((file_name or "<no-file>", classname or "<no-class>", name))
    return identity, file_name, classname, name

def _case(element: ET.Element) -> JUnitCase:
    status = (element.get("status") or "run").lower()
    if status != "run":
        raise JUnitReportError(f"unknown testcase status: {status!r}")
    unknown = {_tag(child) for child in element} - _ALLOWED_CASE_CHILDREN
    if unknown:
        raise JUnitReportError(f"unknown testcase outcome content: {sorted(unknown)}")
    signals = [child for child in element if _tag(child) in {"error", "failure", "skipped"}]
    if len(signals) > 1:
        raise JUnitReportError("testcase has ambiguous duplicate outcomes")
    identity, file_name, classname, name = _identity(element)
    if not signals:
        return JUnitCase(identity, file_name, classname, name, "passed", "call")
    signal = signals[0]
    outcome = _tag(signal)
    if outcome == "skipped" and "xfail" in (signal.get("type") or "").lower():
        outcome = "xfail"
    return JUnitCase(identity, file_name, classname, name, outcome, _phase(signal, outcome))

def _validate_suite(suite: ET.Element) -> None:
    cases = [item for item in suite.iter() if _tag(item) == "testcase"]
    parsed = [_case(item) for item in cases]
    expected = _integer(suite.get("tests"), "tests")
    teardown_errors = sum(
        case.outcome == "error" and case.phase == "teardown" for case in parsed
    )
    valid_totals = {len(cases) - teardown_errors, len(cases), len(cases) + teardown_errors}
    if expected not in valid_totals:
        raise JUnitReportError(
            f"incomplete testsuite: declared {expected} tests but found {len(cases)}"
        )
    for attribute, outcome in _COUNTERS.items():
        expected_count = _integer(suite.get(attribute), attribute)
        actual = (sum(case.outcome in {"skipped", "xfail"} for case in parsed)
                  if outcome == "skipped" else sum(case.outcome == outcome for case in parsed))
        if expected_count != actual:
            raise JUnitReportError(
                f"incomplete testsuite: declared {expected_count} {attribute} but found {actual}"
            )

def _contains_dtd(payload: bytes) -> bool:
    """Detect ASCII XML declarations across UTF-8/16/32 encodings."""
    normalized = payload.replace(b"\x00", b"").upper()
    return b"<!DOCTYPE" in normalized or b"<!ENTITY" in normalized

def _validate_stream(payload: bytes) -> None:
    """Enforce resource limits while parsing, before retaining a full tree."""
    depth = elements = testcases = 0
    try:
        for event, element in ET.iterparse(io.BytesIO(payload), events=("start", "end")):
            if event == "start":
                depth += 1
                elements += 1
                if depth > _MAX_XML_DEPTH:
                    raise JUnitReportError("JUnit XML exceeds maximum nesting depth")
                if elements > _MAX_XML_ELEMENTS:
                    raise JUnitReportError("JUnit XML exceeds maximum element count")
                if _tag(element) == "testcase":
                    testcases += 1
                    if testcases > _MAX_TESTCASES:
                        raise JUnitReportError("JUnit report exceeds testcase limit")
                for name, value in element.attrib.items():
                    if len(name.encode()) > _MAX_XML_ATTRIBUTE_BYTES or len(value.encode()) > _MAX_XML_ATTRIBUTE_BYTES:
                        raise JUnitReportError("JUnit XML attribute exceeds resource limit")
            else:
                for text in (element.text, element.tail):
                    if text is not None and len(text.encode()) > _MAX_XML_TEXT_BYTES:
                        raise JUnitReportError("JUnit XML text exceeds resource limit")
                depth -= 1
                element.clear()
    except ET.ParseError as exc:
        raise JUnitReportError(f"malformed JUnit XML: {exc}") from exc

def _read_payload(report_path: Path, *, nofollow: bool) -> bytes:
    if not nofollow:
        if not report_path.is_file():
            raise JUnitReportError(f"cannot read JUnit report {report_path}: not a regular file")
        try:
            size = report_path.stat().st_size
            with report_path.open("rb") as handle:
                payload = handle.read(_MAX_REPORT_BYTES + 1)
        except OSError as exc:
            raise JUnitReportError(f"cannot read JUnit report {report_path}: {exc}") from exc
    else:
        fd: int | None = None
        try:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(report_path, flags)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise JUnitReportError(f"cannot read JUnit report {report_path}: not a regular file")
            size = os.fstat(fd).st_size
            handle = os.fdopen(fd, "rb")
            fd = None
            with handle:
                payload = handle.read(_MAX_REPORT_BYTES + 1)
        except JUnitReportError:
            raise
        except OSError as exc:
            raise JUnitReportError(f"cannot read JUnit report {report_path}: {exc}") from exc
        finally:
            if fd is not None:
                os.close(fd)
    if size > _MAX_REPORT_BYTES or len(payload) > _MAX_REPORT_BYTES:
        raise JUnitReportError(f"JUnit report exceeds {_MAX_REPORT_BYTES} byte limit")
    return payload

def parse_junit_report(path: str | Path, *, nofollow: bool = False) -> JUnitReport:
    """Parse a complete, bounded JUnit report or raise ``JUnitReportError``."""
    report_path = Path(path)
    try:
        payload = _read_payload(report_path, nofollow=nofollow)
    except JUnitReportError:
        raise
    except OSError as exc:
        raise JUnitReportError(f"cannot read JUnit report {report_path}: {exc}") from exc
    if not payload.strip():
        raise JUnitReportError(f"empty JUnit report: {report_path}")
    if _contains_dtd(payload):
        raise JUnitReportError("DTD/entity declarations are not accepted")
    _validate_stream(payload)
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise JUnitReportError(f"malformed JUnit report {report_path}: {exc}") from exc
    if _tag(root) not in {"testsuite", "testsuites"}:
        raise JUnitReportError(f"unexpected JUnit root element: {_tag(root)!r}")
    suites = [item for item in root.iter() if _tag(item) == "testsuite"]
    if not suites:
        raise JUnitReportError("JUnit report contains no testsuite")
    cases = [item for item in root.iter() if _tag(item) == "testcase"]
    for suite in suites:
        _validate_suite(suite)
    parsed_cases = tuple(_case(item) for item in cases)
    if not parsed_cases:
        raise JUnitReportError("JUnit report contains no testcases")
    debt_keys = [case.debt_key for case in parsed_cases]
    if len(set(debt_keys)) != len(debt_keys):
        raise JUnitReportError("duplicate testcase identity and phase is ambiguous")
    return JUnitReport(parsed_cases)

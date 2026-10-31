"""Small JUnit report builder for comparator contract tests."""
from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr


def case(
    name: str, outcome: str = "passed", *,
    file: str = "components/example/test/test_unit.py",
    classname: str = "test_unit.TestFeature", phase: str = "call",
) -> str:
    attrs = f"name={quoteattr(name)} file={quoteattr(file)} classname={quoteattr(classname)}"
    if outcome == "passed":
        body = ""
    elif phase == "collection":
        body = f'<{outcome} message="collection failure">boom</{outcome}>'
    elif outcome == "failure":
        body = f'<failure message="failed during {phase}">boom</failure>'
    elif outcome == "error":
        body = f'<error message="failed on {phase} with boom">boom</error>'
    elif outcome == "xfail":
        body = '<skipped type="pytest.xfail" message="expected failure" />'
    elif outcome == "skipped":
        body = '<skipped type="pytest.skip" message="not selected" />'
    else:
        body = f"<{escape(outcome)} />"
    return f"<testcase {attrs}>{body}</testcase>"


def report(*cases: str, tests: int | None = None) -> str:
    joined = "".join(cases)
    count = len(cases) if tests is None else tests
    return (
        f'<testsuites><testsuite name="pytest" tests="{count}" '
        f'failures="{joined.count("<failure ")}" errors="{joined.count("<error ")}" '
        f'skipped="{joined.count("<skipped ")}">{joined}</testsuite></testsuites>'
    )


def write_report(path, *cases: str, tests: int | None = None) -> str:
    path.write_text(report(*cases, tests=tests), encoding="utf-8")
    return str(path)


__all__ = ["case", "report", "write_report"]

"""Property tests for identity-based debt comparison invariants."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given, settings, strategies as st

from factory.test.interface import TestRuntime as Runtime
from factory.test.runtime.junit_fixtures import case, write_report

_NAMES = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
).map(lambda value: f"test_{value}")


def compare(base_cases, candidate_cases):
    with TemporaryDirectory() as directory:
        root = Path(directory)
        base = write_report(root / "base.xml", *base_cases)
        candidate = write_report(root / "candidate.xml", *candidate_cases)
        return Runtime(adapter_type="memory").compare_junit(base, candidate)


@settings(max_examples=50)
@given(name=_NAMES, debt=st.sampled_from(["failure", "error"]))
def test_exact_debt_identity_pass_is_the_only_resolution(name, debt) -> None:
    result = compare([case(name, debt)], [case(name)])
    assert result["passed"] is True
    assert result["resolved"][0]["identity"].endswith(f"::{name}")


@settings(max_examples=50)
@given(
    old_name=_NAMES,
    new_name=_NAMES,
    debt=st.sampled_from(["failure", "error"]),
)
def test_new_identity_always_blocks_even_when_old_debt_resolves(
    old_name, new_name, debt
) -> None:
    if old_name == new_name:
        new_name += "_new"
    result = compare(
        [case(old_name, debt)],
        [case(old_name), case(new_name, debt)],
    )
    assert result["passed"] is False
    assert any(item["reason"] == "new_debt" for item in result["blocking"])


@settings(max_examples=50)
@given(name=_NAMES, outcome=st.sampled_from(["skipped", "xfail"]))
def test_skip_like_outcomes_never_erase_debt(name, outcome) -> None:
    result = compare([case(name, "failure")], [case(name, outcome)])
    assert result["passed"] is False
    assert result["blocking"][0]["candidate_outcome"] == outcome

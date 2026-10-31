"""Typed results for identity-based JUnit comparison."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

OUTCOMES = frozenset({"passed", "skipped", "xfail", "failure", "error"})
DEBT_OUTCOMES = frozenset({"failure", "error"})
PHASES = frozenset({"setup", "call", "teardown", "collection"})


@dataclass(frozen=True)
class JUnitCase:
    """One unambiguous pytest testcase observation."""

    identity: str
    file: str
    classname: str
    name: str
    outcome: str
    phase: str

    @property
    def debt_key(self) -> tuple[str, str]:
        """Return the phase-aware debt identity."""
        return self.identity, self.phase

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-compatible representation."""
        return {
            "identity": self.identity,
            "file": self.file,
            "classname": self.classname,
            "name": self.name,
            "outcome": self.outcome,
            "phase": self.phase,
        }


@dataclass(frozen=True)
class JUnitReport:
    """A validated JUnit report."""

    cases: tuple[JUnitCase, ...]

    def summary(self) -> dict[str, object]:
        """Summarize report outcomes."""
        counts = Counter(case.outcome for case in self.cases)
        return {
            "total": len(self.cases),
            "outcomes": {outcome: counts[outcome] for outcome in sorted(OUTCOMES)},
        }


@dataclass
class JUnitComparison:
    """Fail-closed comparison of a base and candidate report."""

    passed: bool = False
    base: dict[str, object] = field(default_factory=dict)
    candidate: dict[str, object] = field(default_factory=dict)
    blocking: list[dict[str, str]] = field(default_factory=list)
    legacy: list[dict[str, str]] = field(default_factory=list)
    resolved: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return the stable MCP/CI response shape."""
        return {
            "passed": self.passed,
            "base": self.base,
            "candidate": self.candidate,
            "blocking": self.blocking,
            "legacy": self.legacy,
            "resolved": self.resolved,
            "errors": self.errors,
        }

"""UI assertions for validating exploration results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re

from .assertion_base import AssertionResult, UIAssertion


@dataclass
class ConsoleClean(UIAssertion):
    """Assert no console errors."""

    max_errors: int = 0
    max_warnings: int = -1
    ignore_patterns: list[str] = field(default_factory=list)

    @property
    def assertion_type(self) -> str:
        return "console_clean"

    def check(self, context: dict[str, Any]) -> AssertionResult:
        messages = context.get("console_messages", [])
        errors, warnings = [], []

        for msg in messages:
            msg_type = msg.get("type", "").lower()
            text = msg.get("text", "")
            if any(re.search(p, text) for p in self.ignore_patterns):
                continue
            if msg_type == "error":
                errors.append(text)
            elif msg_type in ("warn", "warning"):
                warnings.append(text)

        error_ok = len(errors) <= self.max_errors
        warning_ok = self.max_warnings < 0 or len(warnings) <= self.max_warnings
        return AssertionResult(
            passed=error_ok and warning_ok,
            assertion_type=self.assertion_type,
            message=f"Found {len(errors)} errors, {len(warnings)} warnings",
            details={"errors": errors[:5], "warnings": warnings[:5]},
        )

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.assertion_type, "maxErrors": self.max_errors}


@dataclass
class NetworkOK(UIAssertion):
    """Assert no failed network requests."""

    allowed_failures: list[str] = field(default_factory=list)
    max_failures: int = 0

    @property
    def assertion_type(self) -> str:
        return "network_ok"

    def check(self, context: dict[str, Any]) -> AssertionResult:
        requests = context.get("network_requests", [])
        failures = []
        for req in requests:
            status = req.get("status", 0)
            url = req.get("url", "")
            if status >= 400 or status == 0:
                if not any(p in url for p in self.allowed_failures):
                    failures.append({"url": url, "status": status})

        return AssertionResult(
            passed=len(failures) <= self.max_failures,
            assertion_type=self.assertion_type,
            message=f"Found {len(failures)} failed requests",
            details={"failures": failures[:10]},
        )

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.assertion_type, "allowedFailures": self.allowed_failures}


@dataclass
class A11yValid(UIAssertion):
    """Assert accessibility tree is valid."""

    required_landmarks: list[str] = field(default_factory=list)
    check_labels: bool = True

    @property
    def assertion_type(self) -> str:
        return "a11y_valid"

    def check(self, context: dict[str, Any]) -> AssertionResult:
        snapshot = context.get("snapshot", "")
        issues: list[str] = []
        for landmark in self.required_landmarks:
            if landmark.lower() not in snapshot.lower():
                issues.append(f"Missing landmark: {landmark}")
        if self.check_labels and "button" in snapshot.lower() and 'name=""' in snapshot:
            issues.append("Found button without accessible name")

        return AssertionResult(
            passed=len(issues) == 0,
            assertion_type=self.assertion_type,
            message=f"Found {len(issues)} accessibility issues",
            details={"issues": issues},
        )

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.assertion_type, "requiredLandmarks": self.required_landmarks}


@dataclass
class PerformanceBudget(UIAssertion):
    """Assert Core Web Vitals within budget."""

    lcp_ms: int = 2500
    fid_ms: int = 100
    cls: float = 0.1

    @property
    def assertion_type(self) -> str:
        return "performance_budget"

    def check(self, context: dict[str, Any]) -> AssertionResult:
        perf = context.get("performance", {})
        violations: list[str] = []
        if "lcp" in perf and perf["lcp"] > self.lcp_ms:
            violations.append(f"LCP {perf['lcp']}ms > {self.lcp_ms}ms")
        if "fid" in perf and perf["fid"] > self.fid_ms:
            violations.append(f"FID {perf['fid']}ms > {self.fid_ms}ms")
        if "cls" in perf and perf["cls"] > self.cls:
            violations.append(f"CLS {perf['cls']} > {self.cls}")

        return AssertionResult(
            passed=len(violations) == 0,
            assertion_type=self.assertion_type,
            message=f"Performance: {len(violations)} budget violations",
            details={"violations": violations, "metrics": perf},
        )

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.assertion_type, "lcpMs": self.lcp_ms}


@dataclass
class ElementExists(UIAssertion):
    """Assert specific element exists in snapshot."""

    text: str | None = None
    role: str | None = None

    @property
    def assertion_type(self) -> str:
        return "element_exists"

    def check(self, context: dict[str, Any]) -> AssertionResult:
        snapshot = context.get("snapshot", "")
        found = True
        if self.text and self.text not in snapshot:
            found = False
        if self.role and self.role.lower() not in snapshot.lower():
            found = False

        return AssertionResult(
            passed=found,
            assertion_type=self.assertion_type,
            message=f"Element {'found' if found else 'not found'}",
            details={"text": self.text, "role": self.role},
        )

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.assertion_type, "text": self.text, "role": self.role}

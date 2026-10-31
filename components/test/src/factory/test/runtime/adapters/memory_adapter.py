"""In-memory mock adapter for testing the test brick itself.

Provides a controllable test runner for unit testing without
actually executing pytest.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from ..ports import TestResult, TestDiscoveryResult, TestRunner


@dataclass
class MockTestCase:
    """A mock test case for simulation."""

    name: str
    file: str
    status: str = "passed"  # passed, failed, skipped
    duration: float = 0.1
    error_message: str = ""


class MemoryAdapter:
    """In-memory test runner for testing purposes.

    Allows pre-configuring test results for predictable testing.
    """

    def __init__(self) -> None:
        """Initialize the memory adapter."""
        self._test_cases: list[MockTestCase] = []
        self._healthy: bool = True
        self._version: str = "1.0.0-mock"

    def add_test_case(self, test_case: MockTestCase) -> None:
        """Add a mock test case."""
        self._test_cases.append(test_case)

    def add_test_cases(self, test_cases: list[MockTestCase]) -> None:
        """Add multiple mock test cases."""
        self._test_cases.extend(test_cases)

    def clear_test_cases(self) -> None:
        """Clear all mock test cases."""
        self._test_cases.clear()

    def set_healthy(self, healthy: bool) -> None:
        """Set the health status."""
        self._healthy = healthy

    @staticmethod
    def _matches(test_case: MockTestCase, path: str, pattern: str) -> bool:
        file_name = test_case.file.replace("\\", "/")
        scope = path.replace("\\", "/").rstrip("/")
        in_scope = scope in {"", "."} or file_name == scope or file_name.startswith(f"{scope}/")
        if not in_scope:
            return False
        return (fnmatch.fnmatchcase(PurePosixPath(file_name).name, pattern)
                or fnmatch.fnmatchcase(file_name, pattern))

    def _matching_cases(self, path: str, pattern: str) -> list[MockTestCase]:
        return [tc for tc in self._test_cases if self._matches(tc, path, pattern)]

    def run_tests(
        self,
        path: str,
        pattern: str = "test_*.py",
        verbose: bool = False,
    ) -> TestResult:
        """Run mock tests filtered by contained path and file pattern."""
        matching_cases = self._matching_cases(path, pattern)
        if not matching_cases:
            return TestResult(output=f"No tests found matching path: {path}", test_files=[])

        passed = sum(1 for tc in matching_cases if tc.status == "passed")
        failed = sum(1 for tc in matching_cases if tc.status == "failed")
        skipped = sum(1 for tc in matching_cases if tc.status == "skipped")
        duration = sum(tc.duration for tc in matching_cases)
        errors = [tc.error_message for tc in matching_cases if tc.error_message]
        test_files = list(dict.fromkeys(tc.file for tc in matching_cases))

        output_lines = []
        for tc in matching_cases:
            status_char = {"passed": ".", "failed": "F", "skipped": "s"}[tc.status]
            output_lines.append(
                f"{tc.file}::{tc.name} {tc.status.upper()}" if verbose else status_char
            )
        output_lines.extend(["", f"{passed} passed, {failed} failed, {skipped} skipped"])
        return TestResult(
            passed=passed, failed=failed, skipped=skipped, duration=duration,
            output="\n".join(output_lines) if verbose else "".join(output_lines),
            errors=errors, test_files=test_files,
        )

    def discover_tests(
        self,
        path: str,
        pattern: str = "test_*.py",
    ) -> TestDiscoveryResult:
        """Discover mock tests filtered by contained path and file pattern."""
        matching_cases = self._matching_cases(path, pattern)
        return TestDiscoveryResult(
            test_files=list(dict.fromkeys(tc.file for tc in matching_cases)),
            test_count=len(matching_cases), errors=[],
        )

    def health_check(self) -> dict:
        """Check mock health status."""
        if self._healthy:
            return {
                "status": "healthy", "backend": "memory", "version": self._version,
                "test_cases_configured": len(self._test_cases),
            }
        return {
            "status": "unhealthy", "backend": "memory",
            "error": "Mock adapter set to unhealthy",
        }


# Verify protocol compliance
assert isinstance(MemoryAdapter(), TestRunner)

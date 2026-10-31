"""Protocol-based abstractions for test runners.

Defines the TestRunner protocol and TestResult dataclass for
pluggable test execution backends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class TestResult:
    """Result of a test run."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration: float = 0.0
    output: str = ""
    errors: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Total number of tests."""
        return self.passed + self.failed + self.skipped

    @property
    def success(self) -> bool:
        """Whether execution completed without failures or adapter errors."""
        return self.failed == 0 and not self.errors

    def to_dict(self) -> dict:
        """Convert to dictionary for MCP responses."""
        return {
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "total": self.total,
            "duration": self.duration,
            "success": self.success,
            "output": self.output,
            "errors": self.errors,
            "test_files": self.test_files,
        }


@dataclass
class TestDiscoveryResult:
    """Result of test discovery."""

    test_files: list[str] = field(default_factory=list)
    test_count: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for MCP responses."""
        return {
            "test_files": self.test_files,
            "test_count": self.test_count,
            "errors": self.errors,
        }


@runtime_checkable
class TestRunner(Protocol):
    """Protocol for test runner implementations."""

    def run_tests(
        self,
        path: str,
        pattern: str = "test_*.py",
        verbose: bool = False,
    ) -> TestResult:
        """Run tests at the given path.

        Args:
            path: Directory or file path to run tests from.
            pattern: Glob pattern for test file discovery.
            verbose: Whether to include verbose output.

        Returns:
            TestResult with pass/fail counts and output.
        """
        ...

    def discover_tests(
        self,
        path: str,
        pattern: str = "test_*.py",
    ) -> TestDiscoveryResult:
        """Discover tests at the given path.

        Args:
            path: Directory path to search for tests.
            pattern: Glob pattern for test file discovery.

        Returns:
            TestDiscoveryResult with list of test files.
        """
        ...

    def health_check(self) -> dict:
        """Check if the test runner is available.

        Returns:
            Dict with status and version info.
        """
        ...

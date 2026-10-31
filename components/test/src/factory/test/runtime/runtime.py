"""Test runtime with pluggable adapter selection."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from .adapters import MemoryAdapter, PytestAdapter
from .junit_compare import compare_junit_reports
from .ports import TestDiscoveryResult, TestResult, TestRunner

AdapterType = Literal["pytest", "memory"]


class TestRuntime:
    """Runtime for trusted-local test execution and discovery."""

    def __init__(self, root_dir: str | Path = ".", adapter_type: AdapterType = "pytest") -> None:
        self._root_dir = Path(root_dir).resolve()
        self._adapter_type = adapter_type
        self._default_pattern = "test_*.py"
        self._timeout_seconds = 300
        self._default_verbose = False
        self._authoring_enabled = True
        self._adapter: TestRunner = self._create_adapter(adapter_type)

    @classmethod
    def from_env(cls) -> TestRuntime:
        """Create a runtime from TEST_ROOT_DIR and TEST_ADAPTER."""
        root_dir = os.environ.get("TEST_ROOT_DIR", ".")
        adapter_type = os.environ.get("TEST_ADAPTER", "pytest")
        if adapter_type not in ("pytest", "memory"):
            adapter_type = "pytest"
        return cls(root_dir=root_dir, adapter_type=adapter_type)  # type: ignore

    def _create_adapter(self, adapter_type: AdapterType) -> TestRunner:
        if adapter_type == "memory":
            return MemoryAdapter()
        return PytestAdapter(str(self._root_dir), timeout_seconds=self._timeout_seconds)

    @property
    def root_dir(self) -> Path:
        """Return the resolved root without probing adapter health."""
        return self._root_dir

    @property
    def adapter(self) -> TestRunner:
        return self._adapter

    @property
    def adapter_type(self) -> AdapterType:
        return self._adapter_type

    @property
    def default_pattern(self) -> str:
        return self._default_pattern

    @property
    def default_verbose(self) -> bool:
        return self._default_verbose

    @property
    def timeout_seconds(self) -> int:
        return self._timeout_seconds

    @property
    def authoring_enabled(self) -> bool:
        """In-memory authoring is available for each created runtime."""
        return self._authoring_enabled

    def set_default_adapter(self, adapter: AdapterType) -> None:
        """Select and construct the adapter used by later MCP calls."""
        self._adapter_type = adapter
        self._adapter = self._create_adapter(adapter)

    def set_default_timeout(self, timeout_seconds: int) -> None:
        self._timeout_seconds = timeout_seconds
        if hasattr(self._adapter, "timeout_seconds"):
            self._adapter.timeout_seconds = timeout_seconds

    def set_default_pattern(self, pattern: str) -> None:
        self._default_pattern = pattern

    def set_default_verbose(self, verbose: bool) -> None:
        self._default_verbose = verbose

    def set_adapter(self, adapter: TestRunner) -> None:
        """Set a custom adapter, primarily for trusted-local tests."""
        self._adapter = adapter
        if hasattr(self._adapter, "timeout_seconds"):
            self._adapter.timeout_seconds = self._timeout_seconds

    def run_tests(self, path: str = ".", pattern: str = "test_*.py", verbose: bool = False) -> TestResult:
        return self._adapter.run_tests(path, pattern, verbose)

    def run_component_tests(self, component_name: str, verbose: bool = False) -> TestResult:
        return self.run_tests(f"components/{component_name}/test", verbose=verbose)

    def run_all_tests(self, verbose: bool = False) -> TestResult:
        return self.run_tests(".", verbose=verbose)

    def discover_tests(self, path: str = ".", pattern: str = "test_*.py") -> TestDiscoveryResult:
        return self._adapter.discover_tests(path, pattern)

    def compare_junit(
        self, base_report: str | Path, candidate_report: str | Path, *, nofollow: bool = False
    ) -> dict[str, object]:
        """Compare JUnit reports, optionally rejecting final symlink replacement."""
        return compare_junit_reports(base_report, candidate_report, nofollow=nofollow).to_dict()

    def health_check(self) -> dict:
        return self._adapter.health_check()

    def get_info(self) -> dict:
        return {"root_dir": str(self._root_dir), "adapter_type": self._adapter_type,
                "adapter_health": self.health_check()}

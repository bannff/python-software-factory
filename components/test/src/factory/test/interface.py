"""Polylith Interface for test module.

Exposes the public API for the test brick.
"""

from .server import create_mcp_server as create_server
from .runtime.runtime import TestRuntime
from .runtime.ports import TestRunner, TestResult, TestDiscoveryResult
from .runtime.adapters import PytestAdapter, MemoryAdapter
from .runtime.adapters.memory_adapter import MockTestCase
from .runtime.junit_compare import compare_junit_reports
from .runtime.junit_models import JUnitCase, JUnitComparison, JUnitReport
from .runtime.junit_parser import JUnitReportError, parse_junit_report

__all__ = [
    "create_server",
    "TestRuntime",
    "TestRunner",
    "TestResult",
    "TestDiscoveryResult",
    "PytestAdapter",
    "MemoryAdapter",
    "MockTestCase",
    "JUnitCase",
    "JUnitComparison",
    "JUnitReport",
    "JUnitReportError",
    "compare_junit_reports",
    "parse_junit_report",
]

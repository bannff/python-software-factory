"""Core module for test brick.

This module is kept for backward compatibility.
New code should use the runtime module directly.
"""

from .runtime.runtime import TestRuntime
from .runtime.ports import TestResult, TestDiscoveryResult
from .runtime.adapters import PytestAdapter

# Backward compatibility alias
TestRunnerRuntime = TestRuntime

__all__ = [
    "TestRuntime",
    "TestRunnerRuntime",
    "TestResult",
    "TestDiscoveryResult",
    "PytestAdapter",
]

"""Test runner adapters.

Provides pluggable test runner implementations:
- PytestAdapter: Real pytest execution
- MemoryAdapter: In-memory mock for testing
"""

from .pytest_adapter import PytestAdapter
from .memory_adapter import MemoryAdapter

__all__ = ["PytestAdapter", "MemoryAdapter"]

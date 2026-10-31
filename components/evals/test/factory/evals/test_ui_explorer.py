"""Tests for UI Explorer - imports split test modules for discovery."""

# Tests are split across multiple files for compliance:
# - test_ui_actions.py - UI action tests
# - test_ui_assertions.py - UI assertion tests  
# - test_ui_runner.py - Runner and reporter tests

from factory.evals.runtime.ui import UIScenario, UIFinding, FindingSeverity


def test_ui_explorer_module_imports():
    """Verify UI Explorer module imports work."""
    assert UIScenario is not None
    assert UIFinding is not None
    assert FindingSeverity is not None

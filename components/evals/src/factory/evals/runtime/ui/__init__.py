"""UI Explorer for agentic UI testing.

Provides scenarios, actions, assertions, and reporters for
exploring UIs via Chrome DevTools MCP.

Usage:
    from factory.evals.runtime.ui import (
        UIScenario, Click, Fill, WaitFor,
        ConsoleClean, NetworkOK, A11yValid,
    )

    scenario = UIScenario(
        name="Login Flow",
        route="/login",
        actions=[
            Fill("email", "test@example.com"),
            Click("submit"),
            WaitFor("Dashboard"),
        ],
        assertions=[ConsoleClean(), NetworkOK()],
    )
"""

from .scenarios import (
    UIScenario,
    UIAction,
    Click,
    Fill,
    Hover,
    WaitFor,
    Navigate,
    PressKey,
)
from .assertion_base import UIAssertion, AssertionResult
from .assertions import (
    ConsoleClean,
    NetworkOK,
    A11yValid,
    PerformanceBudget,
    ElementExists,
)
from .reporters import (
    UIFinding,
    FindingSeverity,
    UIReporter,
    FileReporter,
    ConsoleReporter,
)

__all__ = [
    # Scenarios
    "UIScenario",
    "UIAction",
    "Click",
    "Fill",
    "Hover",
    "WaitFor",
    "Navigate",
    "PressKey",
    # Assertions
    "UIAssertion",
    "AssertionResult",
    "ConsoleClean",
    "NetworkOK",
    "A11yValid",
    "PerformanceBudget",
    "ElementExists",
    # Reporters
    "UIFinding",
    "FindingSeverity",
    "UIReporter",
    "FileReporter",
    "ConsoleReporter",
]

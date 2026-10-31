"""Command Injection game adapter (OWASP A05).

Agent finds OS command injection vulnerabilities.
Validates that findings reference shell execution context.
"""

from __future__ import annotations

from typing import Any

from .security_base import SecurityGameRules


class CommandInjectionRules(SecurityGameRules):
    """OS command injection vulnerability finding game."""

    game_type: str = "command_injection"

    def _validate_finding(self, move: dict[str, Any]) -> bool:
        """Check for command injection evidence."""
        evidence = move.get("evidence", "")
        return any(
            kw in evidence.lower()
            for kw in ("shell", "exec", "subprocess", "os.system", "popen", "command", "pipe")
        )

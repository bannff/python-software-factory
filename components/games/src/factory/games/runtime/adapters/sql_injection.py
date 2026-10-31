"""SQL Injection game adapter (OWASP A05).

Agent finds SQL injection vulnerabilities in code snippets.
Validates that findings include injection-specific evidence
(query pattern, injection point, parameterization status).
"""

from __future__ import annotations

from typing import Any

from .security_base import SecurityGameRules


class SQLInjectionRules(SecurityGameRules):
    """SQL injection vulnerability finding game."""

    game_type: str = "sql_injection"

    def _validate_finding(self, move: dict[str, Any]) -> bool:
        """Check for injection-specific evidence fields."""
        evidence = move.get("evidence", "")
        return any(
            kw in evidence.lower()
            for kw in ("inject", "sql", "query", "parameteriz", "f-string", "format")
        )

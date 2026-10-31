"""XSS Hunter game adapter (OWASP A05).

Agent traces source-to-sink XSS flows in code.
Validates that findings include DOM/reflected/stored context.
"""

from __future__ import annotations

from typing import Any

from .security_base import SecurityGameRules


class XSSHunterRules(SecurityGameRules):
    """Cross-site scripting vulnerability finding game."""

    game_type: str = "xss_hunter"

    def _validate_finding(self, move: dict[str, Any]) -> bool:
        """Check for XSS-specific evidence fields."""
        evidence = move.get("evidence", "")
        return any(
            kw in evidence.lower()
            for kw in ("xss", "script", "innerhtml", "sink", "source", "reflected", "stored", "dom")
        )

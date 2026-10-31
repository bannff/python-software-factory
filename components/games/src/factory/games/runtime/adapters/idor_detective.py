"""IDOR Detective game adapter (OWASP A01).

Agent finds insecure direct object reference vulnerabilities.
Validates that findings reference authorization/ownership checks.
"""

from __future__ import annotations

from typing import Any

from .security_base import SecurityGameRules


class IDORDetectiveRules(SecurityGameRules):
    """Insecure direct object reference vulnerability finding game."""

    game_type: str = "idor_detective"

    def _validate_finding(self, move: dict[str, Any]) -> bool:
        """Check for IDOR-specific evidence."""
        evidence = move.get("evidence", "")
        return any(
            kw in evidence.lower()
            for kw in ("idor", "authorization", "ownership", "access control", "direct object")
        )

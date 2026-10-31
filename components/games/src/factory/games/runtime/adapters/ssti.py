"""Server-Side Template Injection game adapter (OWASP A05).

Agent finds SSTI vulnerabilities in template rendering code.
Validates that findings reference template engine context.
"""

from __future__ import annotations

from typing import Any

from .security_base import SecurityGameRules


class SSTIRules(SecurityGameRules):
    """Server-side template injection vulnerability finding game."""

    game_type: str = "ssti"

    def _validate_finding(self, move: dict[str, Any]) -> bool:
        """Check for SSTI-specific evidence."""
        evidence = move.get("evidence", "")
        return any(
            kw in evidence.lower()
            for kw in ("template", "jinja", "render", "mako", "twig", "ssti", "sandbox")
        )

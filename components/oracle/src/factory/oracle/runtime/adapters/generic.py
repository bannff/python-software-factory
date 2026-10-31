"""Generic fallback verifier — the domain-agnostic default.

When no verifier is registered for a finding's domain, this returns the
finding's CURRENT state unchanged plus a "no verifier registered" note.
It NEVER raises and NEVER branches on a domain literal — it is the
engine's safety net, not a domain handler (bd python-factory-216ti).
"""

from __future__ import annotations

from typing import Any

_NO_VERIFIER_NOTE = "no verifier registered for this finding's domain"


class GenericFallbackVerifier:
    """Returns the finding's state unchanged; the registry-miss default."""

    name = "generic-fallback"

    def verify(
        self, finding: dict[str, Any], context: dict[str, Any],
    ) -> dict[str, Any]:
        """Echo the current state; attach a no-verifier evidence note."""
        return {
            "state": finding.get("state", "candidate"),
            "evidence": _NO_VERIFIER_NOTE,
            "verifier": self.name,
        }


__all__ = ["GenericFallbackVerifier"]

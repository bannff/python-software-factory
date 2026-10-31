"""Pydantic models for the oracle brick."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class VerifyOutcome(BaseModel):
    """Normalized verifier result.

    ``state`` is a neutral verification state; ``evidence`` is free-form
    (string note or structured dict); ``verifier`` names the producer.
    """

    state: str
    evidence: Any = ""
    verifier: str = "generic-fallback"

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict matching the ``VerifierPort`` contract."""
        return {
            "state": self.state,
            "evidence": self.evidence,
            "verifier": self.verifier,
        }


__all__ = ["VerifyOutcome"]

"""Oracle runtime — registry-overlay verifier dispatch + generic fallback.

Domain selection is PURE registry lookup keyed by a domain/manifest id
with a generic fallback. ZERO domain-equality branches, zero domain
literals, zero cross-brick imports — the discipline that keeps the oracle
agnostic (bd python-factory-216ti, meta-architect verdict ee6a3b0e).

The vNext blockchain provenance anchor (bd python-factory-v689r,
DEFERRED) will dock here as its future home — no anchor logic ships now.
"""

from __future__ import annotations

import logging
from typing import Any

from .adapters.generic import GenericFallbackVerifier
from .registry import VerifierRegistry, get_registry

logger = logging.getLogger(__name__)


class OracleRuntime:
    """Dispatches a finding to its registry-resolved verifier."""

    def __init__(self, registry: VerifierRegistry | None = None) -> None:
        self._registry = registry or get_registry()
        self._fallback = GenericFallbackVerifier()

    @property
    def registry(self) -> VerifierRegistry:
        """The verifier registry backing this runtime."""
        return self._registry

    def resolve_key(self, finding: dict[str, Any], domain: str = "") -> str:
        """Resolve the dispatch key from the explicit arg or finding meta.

        Falls back through ``domain`` → ``finding['domain']`` →
        ``finding['manifest_id']`` → ``""``. This is metadata lookup, not
        a domain branch — every key flows through the same registry.
        """
        return domain or str(
            finding.get("domain") or finding.get("manifest_id") or ""
        )

    def verify(
        self,
        finding: dict[str, Any],
        domain: str = "",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Dispatch to the resolved verifier; generic fallback on miss.

        Never raises: a verifier that throws is downgraded to a
        ``verifying`` outcome with the error captured as evidence.
        """
        ctx = context or {}
        key = self.resolve_key(finding, domain)
        verifier = self._registry.resolve(key) or self._fallback
        name = getattr(verifier, "name", "unknown")
        try:
            outcome = dict(verifier.verify(finding, ctx))
        except Exception as exc:  # never propagate — degrade gracefully
            logger.warning("verifier %r raised: %s", name, exc)
            outcome = {
                "state": finding.get("state", "candidate"),
                "evidence": f"verifier error: {exc}",
                "verifier": name,
            }
        outcome.setdefault("verifier", name)
        outcome.setdefault("state", finding.get("state", "candidate"))
        return outcome


_runtime: OracleRuntime | None = None


def get_runtime() -> OracleRuntime:
    """Return the process-wide oracle runtime."""
    global _runtime
    if _runtime is None:
        _runtime = OracleRuntime()
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (test hygiene)."""
    global _runtime
    _runtime = None

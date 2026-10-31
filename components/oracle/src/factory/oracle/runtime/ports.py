"""Abstract ports for the oracle brick.

``VerifierPort`` is the polymorphic seam: every domain verifier — a
built-in or a pack-supplied piece of DATA — implements ``verify`` and is
dispatched by the registry-overlay in :mod:`runtime.runtime`. The engine
NEVER branches on a domain literal; selection is pure registry lookup
plus a generic fallback (bd python-factory-216ti Contract B).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VerifierPort(Protocol):
    """A domain verifier — pure behavior behind a uniform call.

    Implementations expose a ``name`` (for evidence attribution) and a
    ``verify`` method that returns a neutral outcome dict.
    """

    name: str

    def verify(
        self, finding: dict[str, Any], context: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify a finding and return ``{state, evidence, verifier}``.

        ``state`` is one of the closed neutral set
        {candidate, verifying, verified, refuted}. Implementations SHOULD
        NOT raise on a normal verification outcome — the runtime guards
        against raises but a clean verifier degrades to ``verifying``.
        """
        ...


__all__ = ["VerifierPort"]

"""Generic fallback reward source — the domain-agnostic default.

It abstains (returns ``None``) for every run: it carries no scoring of its
own and exists only so a fresh deployment with no registered sources has a
well-defined, branch-free "no signal" path. It NEVER raises and NEVER
branches on a domain literal (bd python-factory-pfvo9).
"""

from __future__ import annotations

from typing import Any, Callable

from ..models import RewardSignal


class GenericFallbackRewardSource:
    """Always abstains; the registry-empty safety net."""

    source_id = "generic-fallback"

    def signal_or_none(
        self, run_ctx: dict[str, Any], invoker: Callable[..., Any] | None,
    ) -> RewardSignal | None:
        """Abstain — the generic source produces no reward signal."""
        return None


__all__ = ["GenericFallbackRewardSource"]

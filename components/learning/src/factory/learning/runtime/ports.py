"""Abstract ports for the learning brick.

``RewardSourcePort`` is polymorphic: every reward source — a built-in
adapter (``gt-findings``, ``llm-judge``, ``user-feedback``, or ``telemetry``)
or a pack/user extension — implements ``signal_or_none`` and is dispatched by
the registry overlay in :mod:`runtime.runtime`. The engine NEVER branches on
a domain literal; it iterates the registered sources and each source decides
whether it has a signal for the given run (bd python-factory-pfvo9).
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

from .models import RewardSignal


@runtime_checkable
class RewardSourcePort(Protocol):
    """A reward source — pure behavior behind a uniform call.

    Implementations expose a ``source_id`` (for provenance/attribution)
    and a ``signal_or_none`` method that inspects a neutral run context
    and returns a :class:`RewardSignal` when it has signal, else ``None``.
    """

    source_id: str

    def signal_or_none(
        self, run_ctx: dict[str, Any], invoker: Callable[..., Any] | None,
    ) -> RewardSignal | None:
        """Return a reward signal for ``run_ctx``, or ``None`` to abstain.

        ``run_ctx`` is the neutral completion context (run_id, workflow_id,
        domain_class, target_app, …). ``invoker`` is the cross-brick MCP
        tool invoker (or ``None`` if unavailable) — sources reach other
        bricks by tool name, never by import. Implementations SHOULD be
        cheap to abstain and MUST NOT raise (the runtime guards anyway).
        """
        ...


__all__ = ["RewardSourcePort"]

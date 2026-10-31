"""Process-wide registry of evaluator providers — the polymorphic rail.

Adding a judging framework is data: register a provider keyed by its
``framework`` name. Built-ins are seeded lazily in CODE (mirrors the
learning brick's reward-source registry). Importing a provider module must
NOT import its backing SDK — SDKs are imported only inside ``build()`` /
``evaluate()`` so the default deterministic path stays dependency-light.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...ports import EvaluatorProviderPort

__all__ = [
    "register_provider",
    "get_provider",
    "available_frameworks",
    "reset_providers",
]

_PROVIDERS: dict[str, "EvaluatorProviderPort"] = {}
_SEEDED = False


def register_provider(provider: "EvaluatorProviderPort") -> None:
    """Register a provider keyed by its ``framework`` name."""
    _PROVIDERS[provider.framework] = provider


def _ensure_seeded() -> None:
    """Seed the built-in providers once (lazy, SDK-free import)."""
    global _SEEDED
    if _SEEDED:
        return
    _SEEDED = True
    from .deterministic import DeterministicProvider
    from .langchain_provider import LangChainProvider
    from .langchain_trajectory import LangChainTrajectoryProvider
    from .strands_provider import StrandsProvider

    for provider in (
        DeterministicProvider(),
        StrandsProvider(),
        LangChainProvider(),
        LangChainTrajectoryProvider(),
    ):
        register_provider(provider)


def get_provider(framework: str) -> "EvaluatorProviderPort":
    """Resolve a provider by framework name (fail-closed with available list)."""
    _ensure_seeded()
    if framework not in _PROVIDERS:
        raise ValueError(
            f"unknown evaluator framework: {framework}. "
            f"available: {', '.join(sorted(_PROVIDERS))}"
        )
    return _PROVIDERS[framework]


def available_frameworks() -> list[str]:
    """Return all registered framework names, sorted."""
    _ensure_seeded()
    return sorted(_PROVIDERS)


def reset_providers() -> None:
    """Clear the registry and re-seed on next access (test hygiene)."""
    global _SEEDED
    _PROVIDERS.clear()
    _SEEDED = False

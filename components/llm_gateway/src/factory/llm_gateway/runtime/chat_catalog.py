"""Safe, deployment-scoped catalog of chat models (#136)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from .chat_profile import resolve_chat_profile
from .openai_compat_policy import configured_profile_names
from .openrouter_catalog import ModelPricing, openrouter_models, openrouter_pricing


#: The variable that selects the deployment's chat model. Every ambient
#: consumer (the catalog below, side-chat planning) must resolve THIS, so no
#: consumer hand-maintains a default that can diverge from what chat uses.
CONFIGURED_CHAT_MODEL_ENV = "COMPANION_X_CHAT_MODEL"

#: Deployment knob for the served projection. ``full`` restores the pre-#136
#: behavior of always merging the live provider catalog; any other value —
#: including a typo — pins the deployment to the scoped projection, so a
#: malformed value can only narrow, never widen, what a picker offers.
MODEL_CATALOG_SCOPE_ENV = "COMPANION_X_MODEL_CATALOG_SCOPE"

#: Served-scope tokens (mirrored by the ``agent_list_models`` input DTO).
SCOPED = "configured"
FULL = "all"

_FULL_ENV_VALUE = "full"


def configured_chat_model_id() -> str:
    """Return the configured chat model selector ("" when unset)."""
    return os.getenv(CONFIGURED_CHAT_MODEL_ENV, "").strip()


@dataclass(frozen=True, slots=True)
class ChatModelDescriptor:
    """Non-secret model choice suitable for MCP and frontend projection."""

    model_id: str
    provider: str
    model: str
    pricing: ModelPricing | None = None
    configured: bool = True

    @property
    def effective_model_id(self) -> str:
        """The provider-native model this selector resolves to and runs."""
        return f"{self.provider}/{self.model}"


@dataclass(frozen=True, slots=True)
class ChatModelCatalog:
    """One scoped projection plus the rows that scoping withheld (#136)."""

    models: tuple[ChatModelDescriptor, ...]
    scope: str = SCOPED
    hidden_count: int = 0
    unresolved: tuple[str, ...] = ()


def list_chat_models(
    *, refresh: bool = False, scope: str = SCOPED, include: tuple[str, ...] = (),
) -> ChatModelCatalog:
    """List chat choices without exposing endpoints or credential names.

    Deployment config leads (``COMPANION_X_CHAT_MODEL``, then every explicitly
    allowed ``openai-compat`` profile) and the live provider catalog (450+ ids)
    is offered only under ``scope="all"`` or a ``..._SCOPE=full`` deployment — a
    live catalog of 453 ids must never read as 453 configured models (#136).
    Rows sourced from that live catalog carry ``configured=False``; tasks that
    show the effective model read ``effective_model_id``.

    ``include`` names the selectors a caller must be able to resolve (the
    session's own model) and is appended LAST: a deployment-configured row then
    always wins its ``(provider, model)`` slot and keeps ``configured=True``.
    Selectors that cannot resolve are reported in ``unresolved`` rather than
    failing the whole catalog — the pill must be able to say "unavailable".
    """
    default = configured_chat_model_id()
    profiles = configured_profile_names()
    configured_ids = ([default] if default else []) + [
        f"openai-compat/{name}" for name in profiles
    ]
    resolvable, unresolved = _resolvable_includes(include)
    openrouter_active = _openrouter_configured(default)
    pricing_by_model = openrouter_pricing(refresh=refresh) if openrouter_active else {}
    candidates: list[str] = []
    if default:
        candidates.append(default)
    if openrouter_active:
        candidates.extend(
            f"openrouter/{name}" for name in openrouter_models(refresh=refresh)
        )
    candidates.extend(f"openai-compat/{name}" for name in profiles)
    candidates.extend(resolvable)
    if not candidates:
        raise ValueError("chat model catalog unavailable")
    try:
        rows = _project(candidates, configured_ids, pricing_by_model)
    except ValueError as exc:
        raise ValueError("chat model catalog unavailable") from exc
    if not rows:
        raise ValueError("chat model catalog unavailable")
    if _serves_full_scope(scope):
        return ChatModelCatalog(
            models=tuple(rows), scope=FULL, hidden_count=0, unresolved=unresolved,
        )
    required = frozenset(_profile_key(selector) for selector in resolvable)
    scoped = tuple(
        row for row in rows
        if row.configured or (row.provider, row.model) in required
    )
    return ChatModelCatalog(
        models=scoped, scope=SCOPED, hidden_count=len(rows) - len(scoped),
        unresolved=unresolved,
    )


def _project(
    candidates: list[str], configured_ids: list[str],
    pricing_by_model: dict[str, ModelPricing],
) -> list[ChatModelDescriptor]:
    """Resolve candidates in order; the first row for a key wins its slot."""
    result: list[ChatModelDescriptor] = []
    seen: set[tuple[str, str]] = set()
    for model_id in dict.fromkeys(candidates):
        profile = resolve_chat_profile(model_id)
        key = (profile.provider, profile.model)
        if key in seen:
            continue
        seen.add(key)
        result.append(ChatModelDescriptor(
            model_id=model_id, provider=profile.provider, model=profile.model,
            pricing=(
                pricing_by_model.get(profile.model)
                if profile.provider == "openrouter" else None
            ),
            configured=model_id in configured_ids,
        ))
    return result


def _profile_key(selector: str) -> tuple[str, str]:
    profile = resolve_chat_profile(selector)
    return (profile.provider, profile.model)


def _resolvable_includes(
    include: tuple[str, ...],
) -> tuple[list[str], tuple[str, ...]]:
    """Split caller-required selectors into the resolvable ones and the rest."""
    resolvable: list[str] = []
    unresolved: list[str] = []
    for selector in dict.fromkeys(include):
        try:
            resolve_chat_profile(selector)
        except ValueError:
            unresolved.append(selector)
        else:
            resolvable.append(selector)
    return resolvable, tuple(unresolved)


def _serves_full_scope(scope: str) -> bool:
    """The deployment knob wins; an unrecognized value can only narrow."""
    configured = os.getenv(MODEL_CATALOG_SCOPE_ENV, "").strip().lower()
    if configured == _FULL_ENV_VALUE:
        return True
    if configured:
        return False
    return scope == FULL


def _openrouter_configured(default: str) -> bool:
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        return False
    return default == "openrouter" or default.startswith("openrouter/")


__all__ = [
    "CONFIGURED_CHAT_MODEL_ENV",
    "MODEL_CATALOG_SCOPE_ENV",
    "FULL",
    "SCOPED",
    "ChatModelCatalog",
    "ChatModelDescriptor",
    "configured_chat_model_id",
    "list_chat_models",
]

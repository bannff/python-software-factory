"""Per-surface authoring gates: one authority for what the brick may author.

Each surface (skills / steering / agent templates / config) has one
comma-separated allowlist variable naming the ACTIONS it allows. A surface
variable that is set always wins over the legacy blanket switch, and a
value with an unknown token denies the whole surface (a typo must never
widen). Precedence: surface variable, then the legacy ENV switch, then
``settings.authoring.enabled`` — which is consulted ONLY while no surface
variable is set, because settings.yaml is writable by the config surface
itself and letting it participate per-surface would let one grant raise the
rest; with all of that absent, nothing is allowed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from types import MappingProxyType
from typing import Any, Callable, Mapping, TypeVar

logger = logging.getLogger(__name__)

SURFACE_ACTIONS: dict[str, frozenset[str]] = {
    "skills": frozenset({"add", "delete"}),
    "steering": frozenset({"create", "update", "delete"}),
    "agent_templates": frozenset({"create", "delete", "fork", "reset"}),
    "config": frozenset({"read", "write"}),
}
SURFACE_VARIABLES: dict[str, str] = {
    "skills": "FACTORY_AGENT_AUTHORING_SKILLS",
    "steering": "FACTORY_AGENT_AUTHORING_STEERING",
    "agent_templates": "FACTORY_AGENT_AUTHORING_AGENT_TEMPLATES",
    "config": "FACTORY_AGENT_AUTHORING_CONFIG",
}
# Deprecated blanket switch: still means "every surface, every action".
LEGACY_VARIABLE = "SUPER_AGENT_ENABLE_AUTHORING_TOOLS"
_UNAVAILABLE = frozenset()
_TRUTHY = frozenset({"1", "true", "yes", "y", "on"})
F = TypeVar("F", bound=Callable[..., Any])


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in _TRUTHY


@dataclass(frozen=True)
class AuthoringPolicy:
    """Resolved (surface, action) allow matrix for one deployment."""

    allowed: Mapping[str, frozenset[str]] = field(default_factory=dict)
    malformed: tuple[str, ...] = ()

    def allows(self, surface: str, action: str) -> bool:
        return action in self.allowed.get(surface, _UNAVAILABLE)

    def any_allowed(self) -> bool:
        return any(self.allowed.values())


def _parse_surface(surface: str, raw: str, variable: str) -> frozenset[str] | None:
    """Parse one surface flag; ``None`` means malformed (deny everything)."""
    vocabulary = SURFACE_ACTIONS[surface]
    tokens = [token.strip().lower() for token in raw.split(",")]
    unknown = [token for token in tokens if token not in vocabulary and token not in {"all", "none"}]
    if unknown:
        logger.warning(
            "%s=%r has unknown token(s) %s; accepted tokens are %s - denying every '%s' action",
            variable, raw, unknown, sorted(vocabulary | {"all", "none"}), surface,
        )
        return None
    if "none" in tokens:
        return frozenset()
    if "all" in tokens:
        return vocabulary
    return frozenset(tokens)


def settings_authoring_enabled(settings: dict[str, Any] | None) -> bool:
    """Whether ``settings.authoring.enabled`` asks for authoring."""
    block = settings.get("authoring") if isinstance(settings, dict) else None
    return _truthy(block.get("enabled")) if isinstance(block, dict) else False


def authoring_policy(settings: dict[str, Any] | None = None) -> AuthoringPolicy:
    """Resolve: surface flag, legacy env switch, settings (unset-only), deny."""
    configured = {
        surface: os.environ.get(variable, "").strip()
        for surface, variable in SURFACE_VARIABLES.items()
    }
    fallback = _truthy(os.environ.get(LEGACY_VARIABLE))
    if not any(configured.values()):
        # ``settings.yaml`` is writable BY the config surface, so the persisted
        # switch may only ever decide while no per-surface flag is in play —
        # otherwise a config-only grant could widen every other surface.
        fallback = fallback or settings_authoring_enabled(settings)
    allowed: dict[str, frozenset[str]] = {}
    malformed: list[str] = []
    for surface, variable in SURFACE_VARIABLES.items():
        raw = configured[surface]
        if raw:
            parsed = _parse_surface(surface, raw, variable)
            if parsed is None:
                malformed.append(surface)
                parsed = frozenset()
            allowed[surface] = parsed
        else:
            allowed[surface] = SURFACE_ACTIONS[surface] if fallback else frozenset()
    return AuthoringPolicy(allowed=MappingProxyType(allowed), malformed=tuple(malformed))


def gated_tool(
    mcp: Any, policy: AuthoringPolicy, surface: str, action: str,
) -> Callable[[F], F]:
    """Register a tool only when ``policy`` allows ``(surface, action)``.

    A denied tool is handed back unregistered: ``mcp.tool()`` never runs, so
    the tool is absent from ``tools/list`` rather than present-but-denied.
    """
    def decorate(func: F) -> F:
        if policy.allows(surface, action):
            return mcp.tool()(func)
        logger.debug(
            "withholding tool %s: %s/%s is not allowed", func.__name__, surface, action,
        )
        return func
    return decorate


_POLICY_ATTR = "_authoring_policy"


def policy_for(agent: Any) -> AuthoringPolicy:
    """Resolve the policy ONCE per agent (i.e. once per tool catalog).

    Five modules register authoring tools against one catalog; resolving once
    keeps their gates and the capability probe identical, and makes a
    malformed flag log exactly one warning instead of one per module.
    """
    cached = getattr(agent, _POLICY_ATTR, None)
    if isinstance(cached, AuthoringPolicy):
        return cached
    policy = authoring_policy(getattr(agent, "settings", None))
    try:
        setattr(agent, _POLICY_ATTR, policy)
    except AttributeError:
        # Slots-only stand-ins cannot memoise; they still get a correct policy.
        pass
    return policy


__all__ = [
    "AuthoringPolicy", "LEGACY_VARIABLE", "SURFACE_ACTIONS", "SURFACE_VARIABLES",
    "authoring_policy", "gated_tool", "policy_for", "settings_authoring_enabled",
]

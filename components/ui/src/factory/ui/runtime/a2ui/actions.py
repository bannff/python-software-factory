"""ActionRef — the typed wire shape for a view-declared verb (bd:3jcls.3).

An ``ActionRef`` names an MCP tool on an aggregator brick. That is the ONLY
thing it can name. There is deliberately no ``url`` / ``href`` / ``method`` /
``endpoint`` field, and any such key on the raw payload is a hard rejection —
it must be structurally impossible for a view payload to point a click at a
non-MCP target.

Ingestion, not click time. ``parse_action_ref`` runs when a brick's
``*_get_views`` payload crosses into the frontend, so a typo'd tool name
fails loudly at authoring rather than silently at the user's click.

Legacy: 17 bricks already declare ``type: "form"`` with a free-form
``props.tool`` string (e.g. ``agent/mcp/views.py:100`` →
``agent_agent_launch_swarm``). ``normalize_view_actions`` rewrites those into
``props["action"]`` server-side so the frontend learns exactly one shape with
zero back-compat branch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

# Same posture as ``AgentConfig.id`` (bd:67qvz): REJECT, never coerce.
# ``fullmatch`` — ``match`` would let a trailing newline through (the
# discovered bypass in bd:b2d2o).
_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")

# The fixed ``$.``-prefixed grammar already used by ``data_path``
# (``frontends/shared-renderer/src/renderers/renderers-item-list-utils.ts:7``).
# Dotted key walk only — no expressions, no interpolation, no indexing.
_BINDING_RE = re.compile(r"^\$\.[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")

#: Keys that would let a view name a non-MCP target. Presence = rejection.
FORBIDDEN_TARGET_KEYS = frozenset({
    "url", "href", "method", "endpoint", "uri", "src", "target", "path",
})

#: Keys ``parse_action_ref`` understands. Anything else is a typo.
_KNOWN_KEYS = frozenset({
    "brick", "tool", "args", "arg_bindings", "label", "confirm",
    "invalidates", "idempotency_arg",
})

#: Signature of an optional tool-existence probe.
#: ``(brick, tool) -> (resolved_name, input_schema) | None``
ToolResolver = Callable[[str, str], "tuple[str, dict[str, Any]] | None"]


class ActionRefError(ValueError):
    """A view declared an action that cannot be dispatched. Loud by design."""


@dataclass(frozen=True)
class ActionRef:
    """A validated reference to one MCP tool call.

    Attributes:
        brick: Aggregator brick name that owns the tool.
        tool: Brick-local or brick-prefixed tool name.
        args: Literal arguments, merged first.
        arg_bindings: ``param -> "$.path"``, resolved client-side against the
            row/form scope. Overlays ``args``.
        label: Human verb for the control.
        confirm: Require a confirm gesture before dispatch.
        invalidates: View ids / ``data_tool`` names to refetch on success.
        idempotency_arg: Parameter that receives the per-gesture UUID, when
            the target tool's schema actually declares it.
    """

    brick: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    arg_bindings: dict[str, str] = field(default_factory=dict)
    label: str | None = None
    confirm: bool = False
    invalidates: tuple[str, ...] = ()
    idempotency_arg: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for the wire. Keys mirror the field names exactly."""
        return {
            "brick": self.brick,
            "tool": self.tool,
            "args": dict(self.args),
            "arg_bindings": dict(self.arg_bindings),
            "label": self.label,
            "confirm": self.confirm,
            "invalidates": list(self.invalidates),
            "idempotency_arg": self.idempotency_arg,
        }


def _require_token(value: Any, what: str) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise ActionRefError(
            f"action.{what} must match {_TOKEN_RE.pattern!r}, got {value!r}",
        )
    return value


def _require_mapping(value: Any, what: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ActionRefError(f"action.{what} must be an object, got {type(value).__name__}")
    return dict(value)


def parse_action_ref(
    raw: Any,
    *,
    brick_hint: str | None = None,
    resolver: ToolResolver | None = None,
) -> ActionRef:
    """Validate a raw action payload into an :class:`ActionRef`.

    Args:
        raw: The ``props["action"]`` value. A bare string is accepted as
            shorthand for ``{"tool": <string>}`` and needs ``brick_hint``.
        brick_hint: Owning brick, used when the payload omits ``brick``.
            Supplied by the ingestion walker from the ``*_get_views`` source.
        resolver: Optional existence probe. When given, an unresolvable
            ``(brick, tool)`` pair raises — a typo fails at authoring, not at
            click. Also gates ``idempotency_arg`` against the real schema.

    Raises:
        ActionRefError: On any forbidden key, malformed token, unknown key,
            bad binding path, or unresolvable tool.
    """
    if isinstance(raw, str):
        raw = {"tool": raw}
    if not isinstance(raw, dict):
        raise ActionRefError(f"action must be an object or tool string, got {type(raw).__name__}")

    forbidden = FORBIDDEN_TARGET_KEYS & set(raw)
    if forbidden:
        raise ActionRefError(
            f"action may only name an MCP tool; forbidden key(s) {sorted(forbidden)}. "
            "Use brick + tool.",
        )
    unknown = set(raw) - _KNOWN_KEYS
    if unknown:
        raise ActionRefError(f"action has unknown key(s) {sorted(unknown)}")

    brick = _require_token(raw.get("brick") or brick_hint, "brick")
    tool = _require_token(raw.get("tool"), "tool")

    bindings = _require_mapping(raw.get("arg_bindings"), "arg_bindings")
    for param, path in bindings.items():
        if not isinstance(path, str) or not _BINDING_RE.fullmatch(path):
            raise ActionRefError(
                f"action.arg_bindings[{param!r}] must match {_BINDING_RE.pattern!r}, "
                f"got {path!r}",
            )

    invalidates_raw = raw.get("invalidates") or []
    if not isinstance(invalidates_raw, (list, tuple)):
        raise ActionRefError("action.invalidates must be a list")
    invalidates = tuple(str(v) for v in invalidates_raw)

    idempotency_arg = raw.get("idempotency_arg")
    if idempotency_arg is not None and not isinstance(idempotency_arg, str):
        raise ActionRefError("action.idempotency_arg must be a string or null")

    if resolver is not None:
        resolved = resolver(brick, tool)
        if resolved is None:
            raise ActionRefError(f"action names unknown tool {tool!r} on brick {brick!r}")
        _, schema = resolved
        if idempotency_arg and idempotency_arg not in _schema_params(schema):
            # Not fatal: the FE falls back to at-most-once-per-gesture.
            idempotency_arg = None

    return ActionRef(
        brick=brick,
        tool=tool,
        args=_require_mapping(raw.get("args"), "args"),
        arg_bindings=bindings,
        label=raw.get("label"),
        confirm=bool(raw.get("confirm", False)),
        invalidates=invalidates,
        idempotency_arg=idempotency_arg,
    )


def _schema_params(schema: dict[str, Any] | None) -> set[str]:
    """Extract declared parameter names from a JSON-schema-ish dict."""
    props = (schema or {}).get("properties")
    return set(props) if isinstance(props, dict) else set()

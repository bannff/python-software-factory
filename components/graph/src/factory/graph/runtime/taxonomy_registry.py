"""Per-domain graph taxonomy registry.

bd:python-factory-qm07q (epic python-factory-hadbi). Lets non-security
domains (wine pairing, workouts, anything-but-security) declare their own
node types / relationship types / id conventions and have them surface
through the existing ``graph://schemas/taxonomy/{domain}`` MCP resource
template without mutating the security default.

Design choice: **module-global dict with ``reset_extensions`` for tests**.
Picked over the ``mcp_utils.set_service`` route because:

* Same shape as ``mcp_utils.correlation._CANONICAL_KEYS`` — simple, tested.
* No cross-brick caller exists yet; service-registry would be premature.
* Keeps the brick self-contained (graph brick owns its own extension table).
* ``reset_extensions`` gives test isolation explicitly — test fixtures must
  call it in setUp/tearDown to avoid bleed.

Append-only semantics. Re-registering an existing ``domain_id`` raises
``ValueError`` (loud-fail catches typos / accidental double-registration).

The literal security default lives in ``..mcp.docs_security_taxonomy``;
``resolve_domain_taxonomy("security")`` returns it verbatim without
consulting the registry. This matches meta-architect verdict
2efd2a40 Q3 — security CWE/OCSF vocab is the documented default,
**not** a registered extension.

bd:python-factory-qm07q | meta-architect: 2efd2a40 | strands-expert: n/a
"""
from __future__ import annotations

import copy
from typing import Any

# Domain id -> {node_types, relationship_types, conventions}
_EXTENSIONS: dict[str, dict[str, Any]] = {}


def register_extension(
    domain_id: str,
    *,
    node_types: dict[str, Any],
    relationship_types: dict[str, Any],
    conventions: dict[str, Any] | None = None,
) -> None:
    """Register a per-domain taxonomy extension.

    Append-only. ``domain_id`` collisions raise ``ValueError`` rather than
    silently last-write-wins — registry typos are caught at import time.

    Args:
        domain_id: Unique short slug (e.g. ``wine_pairing``, ``workouts``).
        node_types: Node-type dict (same shape as the security
            ``GRAPH_TAXONOMY['node_types']`` entries).
        relationship_types: Relationship-type dict (same shape as the
            security ``GRAPH_TAXONOMY['relationship_types']`` entries).
        conventions: Optional id-format / cross-domain notes dict.

    Raises:
        ValueError: When ``domain_id`` is already registered.
    """
    if domain_id in _EXTENSIONS:
        raise ValueError(f"domain_id '{domain_id}' already registered")
    _EXTENSIONS[domain_id] = {
        "node_types": dict(node_types),
        "relationship_types": dict(relationship_types),
        "conventions": dict(conventions or {}),
    }


def get_extensions() -> dict[str, dict[str, Any]]:
    """Return a frozen-snapshot copy of the registered extensions.

    Mutations to the returned dict (or any nested dict) MUST NOT affect
    the registry. Callers that want to iterate domain ids over time
    should call this on each pass — the snapshot is intentionally cheap.
    """
    return copy.deepcopy(_EXTENSIONS)


def merge_taxonomies(*tax: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge ``node_types`` and ``relationship_types`` across taxonomies.

    Pure helper — no I/O, no mutation of inputs. Last writer wins on key
    collisions inside the same merge call (matches Python ``dict`` update
    order). Conventions are shallow-merged at the top level only.

    Empty arg list returns an empty taxonomy skeleton.
    """
    merged: dict[str, Any] = {
        "node_types": {},
        "relationship_types": {},
        "conventions": {},
    }
    for t in tax:
        if not isinstance(t, dict):
            continue
        for key in ("node_types", "relationship_types", "conventions"):
            section = t.get(key)
            if isinstance(section, dict):
                merged[key].update(section)
        # Preserve top-level metadata fields (version/description) from the
        # last taxonomy that supplies them. The base security taxonomy is
        # passed first, so a later extension overrides only if it sets these.
        for top in ("version", "description"):
            if top in t:
                merged[top] = t[top]
    return merged


def resolve_domain_taxonomy(domain_id: str) -> dict[str, Any] | None:
    """Resolve a per-domain taxonomy view.

    * ``security`` -> the focused ``SECURITY_TAXONOMY`` (the existing pipeline
      view at ``graph://schemas/security-taxonomy``). Built-in default; not
      stored in the registry.
    * Registered extension -> security base merged with the single matching
      extension (per Q3 / Q4 verdict — one extension at a time, security
      always seeds the base).
    * Unknown -> ``None`` (callers should surface a 404-shape error).
    """
    if domain_id == "security":
        from ..mcp.docs_security_taxonomy import SECURITY_TAXONOMY
        return copy.deepcopy(SECURITY_TAXONOMY)
    ext = _EXTENSIONS.get(domain_id)
    if ext is None:
        return None
    from ..mcp.docs_security_taxonomy import SECURITY_TAXONOMY
    base: dict[str, Any] = {
        "version": SECURITY_TAXONOMY.get("version"),
        "description": SECURITY_TAXONOMY.get("description"),
        "node_types": dict(SECURITY_TAXONOMY.get("node_labels", {})),
        "relationship_types": dict(SECURITY_TAXONOMY.get("relationship_types", {})),
        "conventions": dict(SECURITY_TAXONOMY.get("conventions", {})),
    }
    extension_block = {
        "node_types": dict(ext.get("node_types", {})),
        "relationship_types": dict(ext.get("relationship_types", {})),
        "conventions": dict(ext.get("conventions", {})),
    }
    return merge_taxonomies(base, extension_block)


def reset_extensions() -> None:
    """Drop every registered extension. **Test-only.**

    Production callers must NOT invoke this — extensions are append-only
    by contract. Tests should call this in ``setUp`` / ``tearDown`` (or a
    ``pytest`` autouse fixture) to keep the module-global table from
    bleeding across cases.
    """
    _EXTENSIONS.clear()

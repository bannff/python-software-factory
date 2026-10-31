"""Canonical lesson identity helpers."""
from __future__ import annotations

import hashlib

from factory.mcp_utils.interface import protected_canonical_json


def normalized_rule(rule: str) -> str:
    value = rule.lower().strip()
    if not value:
        raise ValueError("lesson rule must not be blank")
    return value


def lesson_identity(
    tenant_id: str, owner_id: str, rule: str,
    scope: str, scope_id: str | None,
) -> tuple[str, str]:
    key = hashlib.sha256(protected_canonical_json({
        "tenant_id": tenant_id, "owner_id": owner_id,
        "rule": normalized_rule(rule), "scope": scope,
        "scope_id": scope_id,
    })).hexdigest()
    return key, f"les_{key[:32]}"


def import_scope(repo_scope: str) -> tuple[str, str | None]:
    """Map a KiroCrew ``repo_scope`` onto the factory scope pair.

    A non-empty repo scope becomes a persona-scoped lesson keyed by the repo,
    preserving scoped-identity separation; an empty scope stays global.
    """
    return ("persona", repo_scope) if repo_scope else ("global", None)


def import_target_digest(
    tenant_id: str, owner_id: str, source_adapter: str, source_record_id: str,
    rule: str, negative: str | None, category: str, repo_scope: str,
    evidence: tuple[str, ...],
) -> str:
    """Recompute the lowercase SHA-256 canonical target digest for an import.

    Binds the source record identity to the exact normalized target lesson
    identity and its content clauses, so a forged digest is refused before any
    write. Computed from the wire fields alone (single source of truth shared
    with the trusted Migration caller).
    """
    scope, scope_id = import_scope(repo_scope)
    identity, lesson_id = lesson_identity(tenant_id, owner_id, rule, scope, scope_id)
    return hashlib.sha256(protected_canonical_json({
        "source_adapter": source_adapter, "source_record_id": source_record_id,
        "identity_key": identity, "lesson_id": lesson_id,
        "rule": normalized_rule(rule), "negative": negative,
        "category": category, "scope": scope, "scope_id": scope_id,
        "evidence": list(evidence),
    })).hexdigest()


__all__ = [
    "import_scope", "import_target_digest", "lesson_identity", "normalized_rule",
]

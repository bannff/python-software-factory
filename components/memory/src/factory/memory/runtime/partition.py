"""Owner-partitioned logical Memory namespace derivation (M6.5 slice 3).

A Crew selects only a logical, owner-partitioned namespace; the project-selected
adapter stays fixed. Owner and scope are validated separately, then the adapter
``user_id`` is derived exactly once as
``sha256(owner_utf8).hexdigest() + "." + memory_scope``.

The owner component is a fixed-width 64-char hex digest and the ``.`` delimiter
is absent from the scope alphabet, so no delimiter ambiguity or metadata-filter
bypass is possible. Scope is a partition key, never a tag / post-filter /
backend. Unidentified, empty, or credential-shaped scope requests fail closed.
"""
from __future__ import annotations

import hashlib
import re

# Bounded lowercase grammar; 128-char cap keeps the derived user_id (64 hex + 1
# delimiter + <=128 scope = <=193) under the adapter's 256-char user_id bound.
_SCOPE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")

# Known credential shapes accepted by the scope alphabet, rejected fail-closed.
# Mirrors the precedent in ``llm_gateway.openai_compat_policy`` and
# ``session.send_ids`` (each brick owns its own copy; no cross-brick import).
_CREDENTIALS = (
    re.compile(r"gh[pousr]_[a-z0-9_]{20,}"),
    re.compile(r"github_pat_[a-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj_)?[a-z0-9_-]{20,}"),
    re.compile(r"(?:sk|pk)_(?:live|test)_[a-z0-9_]{16,}"),
    re.compile(r"xox[baprs]-[a-z0-9-]{10,}"),
)

SAFE_SCOPE_ERROR = "invalid memory scope"
SAFE_OWNER_ERROR = "invalid memory owner"


def credential_clean_scope(value: str) -> bool:
    """Accept only bounded scope identifiers that are not credential-shaped."""
    return bool(_SCOPE_RE.fullmatch(value)) and not any(
        pattern.fullmatch(value) for pattern in _CREDENTIALS
    )


def validate_memory_scope(memory_scope: str) -> str:
    """Return a nonempty, bounded, credential-clean scope or fail closed."""
    if not isinstance(memory_scope, str) or not credential_clean_scope(memory_scope):
        raise ValueError(SAFE_SCOPE_ERROR)
    return memory_scope


def validate_owner_id(owner_id: str) -> str:
    """Return a nonempty, bounded owner identity or fail closed."""
    if (
        not isinstance(owner_id, str)
        or not owner_id.strip()
        or len(owner_id) > 256
        or any(ord(char) < 32 or ord(char) == 127 for char in owner_id)
    ):
        raise ValueError(SAFE_OWNER_ERROR)
    return owner_id


def derive_memory_user_id(owner_id: str, memory_scope: str) -> str:
    """Derive the adapter partition key from separately validated inputs.

    ``sha256(owner_utf8).hexdigest() + "." + memory_scope``. The formula is the
    single Memory-owned source of truth; callers pass the result as the adapter
    ``user_id`` and never re-implement it or post-filter on scope.
    """
    owner = validate_owner_id(owner_id)
    scope = validate_memory_scope(memory_scope)
    digest = hashlib.sha256(owner.encode("utf-8")).hexdigest()
    return f"{digest}.{scope}"


__all__ = [
    "SAFE_OWNER_ERROR",
    "SAFE_SCOPE_ERROR",
    "credential_clean_scope",
    "derive_memory_user_id",
    "validate_memory_scope",
    "validate_owner_id",
]

"""Pydantic v2 contracts for the domain brick (bd:python-factory-w7i8k).

``PresentationManifest`` is the manifest/engagement analog of the agent
brick's persona registry. ``domain_id`` is charset-locked (lowercase,
path-safe) and REJECT-not-coerce, copied verbatim from
``AgentConfig._validate_id`` (bd-67qvz). Every model is ``extra="forbid"``.

Generic-by-default, enriched-by-data: ``domain_id`` is the only required
field; everything else defaults to a generic/empty value so an absent
manifest is byte-identical to ``GENERIC_MANIFEST``.

N2 (strands-expert 69ad7193): persona stays manifest-agnostic. The ONLY
link from a manifest to a persona is ``default_persona_id`` — a SOFT,
dangling-allowed reference resolved-or-skipped, NEVER resolved-or-failed.
There is NO reverse field on ``AgentConfig``.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

# domain_id charset: lowercase alnum + ``-``/``_``, first char alnum,
# <=128 chars; lowercase-only so a case-fold can't collapse two ids onto
# one path/key (bd-67qvz). Copied verbatim from ``AgentConfig._AGENT_ID_RE``.
_DOMAIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")


def _utc_now_iso() -> str:
    """ISO-8601 UTC timestamp (Engagement.created_at default factory)."""
    return datetime.now(timezone.utc).isoformat()


def _validate_charset_id(v: str, field: str) -> str:
    # REJECT (never coerce): ``Security``->``security`` could collide with
    # an existing ``security``, just relocating the bug (bd-67qvz).
    if not _DOMAIN_ID_RE.fullmatch(v):
        raise ValueError(
            f"{field}={v!r} is invalid; must match "
            r"^[a-z0-9][a-z0-9_-]{0,127}$ "
            "(lowercase letters/digits/'-'/'_', first char alnum)"
        )
    return v


class TypeDescriptor(BaseModel):
    """Presentation descriptor for one OPAQUE type code (NO hardcoded CWE)."""
    label: str
    color: str = ""
    icon: str = ""
    description: str | None = None
    model_config = ConfigDict(extra="forbid")


class ThemeAccents(BaseModel):
    """Minimal theme accent palette — all defaulted, kept tiny."""
    primary: str = ""
    accent: str = ""
    severity_high: str = ""
    model_config = ConfigDict(extra="forbid")


class PresentationManifest(BaseModel):
    """Render-side presentation manifest for a domain.

    ``domain_id`` is the only required field; all maps/optionals default
    to generic/empty so an absent manifest == ``GENERIC_MANIFEST``
    byte-for-byte. Taxonomy is NEVER embedded here — ``taxonomy_ref`` is a
    SOFT slug into the graph brick's ``graph://schemas/taxonomy/{domain}``
    resource (taxonomy stays graph's job, DRY).
    """
    domain_id: str
    display_name: str = ""
    # engine-canonical term → domain term (e.g. "finding"→"vulnerability").
    # Empty = engine-neutral terms.
    labels: dict[str, str] = Field(default_factory=dict)
    taxonomy_ref: str | None = None
    # keyed by OPAQUE code — NO hardcoded CWE.
    type_descriptors: dict[str, TypeDescriptor] = Field(default_factory=dict)
    severity_palette: dict[str, str] = Field(default_factory=dict)
    # hints only — layout stays brick-declared views.py.
    artifact_renderers: dict[str, str] = Field(default_factory=dict)
    theme: ThemeAccents | None = None
    # manifest→persona SOFT ref, generic fallback. ONLY persona link.
    default_persona_id: str | None = None
    version: str = "1"
    model_config = ConfigDict(extra="forbid")

    @field_validator("domain_id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        return _validate_charset_id(v, "PresentationManifest.domain_id")


class Engagement(BaseModel):
    """Workspace-scoped active engagement pin (WORKSPACE axis)."""
    id: str
    domain_id: str
    persona_id: str | None = None
    name: str = ""
    created_at: str = Field(default_factory=_utc_now_iso)
    model_config = ConfigDict(extra="forbid")

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        return _validate_charset_id(v, "Engagement.id")


# Module-level generic baseline — the byte-identical-on-absence default
# (analog of persona ``companion-x-default``). All maps {}, all optionals
# None. ``get_manifest`` returns THIS for any unknown domain_id.
GENERIC_MANIFEST = PresentationManifest(domain_id="generic")


__all__ = [
    "TypeDescriptor",
    "ThemeAccents",
    "PresentationManifest",
    "Engagement",
    "GENERIC_MANIFEST",
]

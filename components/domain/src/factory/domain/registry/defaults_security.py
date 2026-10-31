"""Security presentation manifest — pack #1 (bd:python-factory-w7i8k).

A real but minimal manifest for the security domain. Mirrors the agent
brick's per-domain ``defaults_<domain>.py`` split. ``labels`` maps the
engine-canonical term ``finding`` to the domain term ``vulnerability``;
``type_descriptors`` are keyed by OPAQUE codes (NO hardcoded CWE constants
in the model). ``default_persona_id`` softly points at the existing
``security-analyst`` persona (an agent-brick built-in, see
``registry/defaults.SECURITY_AGENTS``); the reference is dangling-allowed
— resolve-or-skip, never resolve-or-fail (N2).
"""
from __future__ import annotations

from ..runtime.models import PresentationManifest, ThemeAccents, TypeDescriptor

SECURITY_MANIFEST = PresentationManifest(
    domain_id="security",
    display_name="Security",
    labels={
        "finding": "vulnerability",
        "target": "asset",
    },
    # SOFT slug into graph://schemas/taxonomy/{domain} — taxonomy stays
    # graph's job; we only reference it, never embed it.
    taxonomy_ref="security",
    type_descriptors={
        # OPAQUE codes — NOT CWE numbers. Domain-supplied severity buckets.
        "high": TypeDescriptor(
            label="High Severity",
            color="#d9534f",
            icon="shield-exclamation",
            description="High-impact vulnerability requiring prompt remediation.",
        ),
        "info": TypeDescriptor(
            label="Informational",
            color="#5bc0de",
            icon="information-circle",
        ),
    },
    severity_palette={
        "high": "#d9534f",
        "medium": "#f0ad4e",
        "low": "#5bc0de",
    },
    artifact_renderers={"finding": "table"},
    theme=ThemeAccents(
        primary="#1f2933",
        accent="#d9534f",
        severity_high="#d9534f",
    ),
    default_persona_id="security-analyst",
    version="1",
)

__all__ = ["SECURITY_MANIFEST"]

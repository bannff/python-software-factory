"""Best-effort taxonomy enrichment helpers for graph persistence.

All functions are silent on failure — they must never break the
persist operation. Lazy imports avoid import-time coupling to
taxonomy modules.
"""

from __future__ import annotations


def enrich_finding_cwe(finding_id: str, cwe_value: str) -> None:
    """Create CLASSIFIED_AS edge from Finding to CWECategory (best-effort)."""
    try:
        from factory.security.runtime.cwe_taxonomy import classify_finding
        classify_finding(finding_id, cwe_value)
    except Exception:
        pass


def enrich_ocsf(entity_id: str, class_uid: int = 2001) -> None:
    """Create CONFORMS_TO edge to OCSFEventClass (best-effort)."""
    try:
        from factory.security.runtime.ocsf_taxonomy import conform_finding
        conform_finding(entity_id, class_uid)
    except Exception:
        pass

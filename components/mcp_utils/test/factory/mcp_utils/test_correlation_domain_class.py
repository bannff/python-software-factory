"""Correlation-pipeline tests for the new ``domain_class`` canonical key.

bd python-factory-sm1va — appends ``domain_class`` to ``_CANONICAL_KEYS``
so domain-agnostic correlation flows through the cross-brick activity +
graph correlation pipeline alongside ``vuln_class``. Per the
meta-architect Q3 typo correction the symbol is ``_CANONICAL_KEYS`` (NOT
``_PROPAGATED_KEYS`` as proposed), and per Q2 ``domain_class`` does NOT
alias onto ``vuln_class`` — both fields propagate independently so
divergent values are preserved.
"""

from __future__ import annotations

from factory.mcp_utils.correlation import (
    _ALIASES,
    _CANONICAL_KEYS,
    correlation_attributes,
    merge_correlation_fields,
    normalize_correlation,
)


def test_domain_class_in_canonical_keys() -> None:
    """Schema-level test: domain_class is part of the canonical set."""
    assert "domain_class" in _CANONICAL_KEYS


def test_domain_class_not_aliased() -> None:
    """domain_class does NOT alias onto vuln_class — divergent values OK."""
    assert "domain_class" not in _ALIASES
    # vuln_class also stays independent (no alias).
    assert "vuln_class" not in _ALIASES


def test_domain_class_propagates_through_normalize() -> None:
    """Normalize lifts domain_class out of payload sources."""
    correlation = normalize_correlation(
        {"domain_class": "wine", "vuln_class": "TASTING"},
    )
    assert correlation["domain_class"] == "wine"
    assert correlation["vuln_class"] == "TASTING"


def test_domain_class_preserved_when_diverges_from_vuln_class() -> None:
    """Divergent domain_class + vuln_class both survive the merge."""
    payload: dict = {}
    merged = merge_correlation_fields(
        payload,
        {"domain_class": "security_idor", "vuln_class": "IDOR"},
    )
    assert merged["domain_class"] == "security_idor"
    assert merged["vuln_class"] == "IDOR"


def test_domain_class_attributes_strict_scalar() -> None:
    """correlation_attributes serializes domain_class for event metadata."""
    attrs = correlation_attributes({"domain_class": "workout"})
    assert attrs.get("domain_class") == "workout"

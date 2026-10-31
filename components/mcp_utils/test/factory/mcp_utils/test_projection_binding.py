"""Closed projection operation binding contracts."""
from __future__ import annotations

import pytest

from factory.mcp_utils.interface import ProjectionBinding, service_only
from factory.mcp_utils.service_bindings import binding_kind, binding_matches


def _binding(**changes) -> ProjectionBinding:
    values = {
        "tenant_id": "tenant", "owner_id": "owner",
        "event_type": "graph.projection.requested", "subject_id": "lesson-1",
        "revision": 2, "payload_digest": "a" * 64,
    }
    values.update(changes)
    return ProjectionBinding(**values)


def test_projection_binding_is_exact_and_validated() -> None:
    binding = _binding()
    assert binding_kind(binding) == "projection"
    values = {field: getattr(binding, field) for field in binding.__dataclass_fields__}
    assert binding_matches(binding, values)
    for field in values:
        replacement = 9 if field == "revision" else "wrong"
        assert not binding_matches(binding, {**values, field: replacement})
    with pytest.raises(ValueError, match="payload_digest"):
        _binding(payload_digest="bad")
    with pytest.raises(ValueError, match="revision"):
        _binding(revision=True)


def test_service_only_accepts_projection_binding() -> None:
    @service_only(callers={"events"}, binding="projection")
    def project() -> None:
        return None

    assert project._mcp_service_binding == "projection"

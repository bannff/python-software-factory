from __future__ import annotations

import pytest

from factory.mcp_utils.interface import LessonProposalBinding, service_only
from factory.mcp_utils.service_bindings import binding_kind, binding_matches


def _binding(**changes) -> LessonProposalBinding:
    values = {
        "tenant_id": "tenant", "owner_id": "owner",
        "source_ref": "feedback-1", "proposal_digest": "a" * 64,
    }
    values.update(changes)
    return LessonProposalBinding(**values)


def test_lesson_proposal_binding_is_exact_and_validated() -> None:
    binding = _binding()
    assert binding_kind(binding) == "lesson_proposal"
    values = {field: getattr(binding, field) for field in binding.__dataclass_fields__}
    assert binding_matches(binding, values)
    for field in values:
        assert not binding_matches(binding, {**values, field: "wrong"})
    with pytest.raises(ValueError, match="digest"):
        _binding(proposal_digest="bad")


def test_service_only_accepts_lesson_proposal_binding() -> None:
    @service_only(callers={"events", "agent"}, binding="lesson_proposal")
    def propose() -> None:
        return None

    assert propose._mcp_service_binding == "lesson_proposal"

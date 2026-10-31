from __future__ import annotations

import pytest

from factory.mcp_utils.interface import CompletionBinding, service_only
from factory.mcp_utils.service_bindings import binding_kind, binding_matches


def _binding(**changes) -> CompletionBinding:
    values = {
        "tenant_id": "tenant", "owner_id": "owner", "session_id": "session",
        "run_id": "run:1", "revision": 1, "result_digest": "a" * 64,
    }
    values.update(changes)
    return CompletionBinding(**values)


def test_completion_binding_is_exact_and_validated() -> None:
    binding = _binding()
    assert binding_kind(binding) == "completion"
    values = {field: getattr(binding, field) for field in binding.__dataclass_fields__}
    assert binding_matches(binding, values)
    for field in values:
        assert not binding_matches(binding, {**values, field: "wrong"})
    with pytest.raises(ValueError, match="revision"):
        _binding(revision=0)
    with pytest.raises(ValueError, match="digest"):
        _binding(result_digest="bad")


def test_service_only_accepts_completion_binding() -> None:
    @service_only(callers={"workflow"}, binding="completion")
    def record() -> None:
        return None

    assert record._mcp_service_binding == "completion"

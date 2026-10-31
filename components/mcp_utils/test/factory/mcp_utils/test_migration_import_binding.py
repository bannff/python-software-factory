"""Exact protected Migration import binding tests."""
from __future__ import annotations

import pytest

from factory.mcp_utils.interface import (
    MigrationImportBinding, service_binding, service_only,
)
from factory.mcp_utils.service_bindings import binding_matches


def _binding(**changes) -> MigrationImportBinding:
    values = {
        "tenant_id": "tenant", "owner_id": "owner",
        "source_adapter": "kirocrew-v1", "source_fingerprint": "a" * 64,
        "plan_digest": "b" * 64, "kind": "memory",
        "source_record_id": "c" * 64, "target_digest": "d" * 64,
    }
    values.update(changes)
    return MigrationImportBinding(**values)


def test_binding_validates_and_matches_exact_identity_fields() -> None:
    binding = _binding()
    arguments = dict(binding.__dict__) if hasattr(binding, "__dict__") else {
        field: getattr(binding, field) for field in binding.__dataclass_fields__
    }
    arguments["content"] = "target-owned payload"
    assert binding_matches(binding, arguments)
    assert not binding_matches(binding, {**arguments, "target_digest": "e" * 64})


def test_service_only_accepts_migration_import_kind() -> None:
    @service_only(callers={"migration"}, binding="migration_import")
    def target() -> None:
        return None

    assert service_binding(target) == "migration_import"


@pytest.mark.parametrize("field,value", [
    ("source_adapter", "Bad Adapter"), ("kind", "Memory"),
    ("source_record_id", "short"), ("source_fingerprint", "x" * 64),
    ("plan_digest", "a" * 63), ("target_digest", "a" * 65),
])
def test_binding_rejects_invalid_fields(field: str, value: str) -> None:
    with pytest.raises(ValueError):
        _binding(**{field: value})

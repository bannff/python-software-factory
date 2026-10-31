"""Direct Cedar and identifier serialization regressions."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from factory.permissions.authoring import _ensure_id
from factory.permissions.runtime.evaluation.aws import _validate_id
from factory.permissions.runtime.evaluation.cedar_adapter import CedarEvaluatorAdapter


def test_local_and_aws_identifiers_reject_controls_and_trailing_newline() -> None:
    for validator in (_ensure_id, _validate_id):
        for value in ("valid\n", "valid\r", "valid\x00", "valid\t"):
            with pytest.raises(ValueError):
                validator(value)


def test_cedar_adapter_quotes_ids_without_raw_interpolation(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeCedar:
        def evaluate(self, request: object) -> object:
            captured["request"] = request
            return SimpleNamespace(decision="allow", diagnostics=[], determining_policies=[])

        def health_check(self) -> dict[str, object]:
            return {"healthy": True}

    monkeypatch.setattr("factory.permissions.runtime.evaluation.cedar_adapter.CedarAdapter", lambda _path=None: FakeCedar())
    adapter = CedarEvaluatorAdapter()
    adapter.evaluate(
        action='read"\\\n',
        resource={"type": "Document", "id": 'doc"\\\n'},
        context={}, principal_id='user"\\\n',
    )
    request = captured["request"]
    assert request.principal == 'User::"user\\\"\\\\\\n"'
    assert request.action == 'Action::"read\\\"\\\\\\n"'
    assert request.resource == 'Document::"doc\\\"\\\\\\n"'


def test_cedar_adapter_rejects_invalid_entity_type() -> None:
    adapter = CedarEvaluatorAdapter()
    with pytest.raises(ValueError, match="Invalid Cedar entity type"):
        adapter.evaluate(action="read", resource={"type": "Document Type", "id": "d1"}, context={})
    with pytest.raises(ValueError, match="Invalid Cedar entity type"):
        adapter.evaluate(action="read", resource={"type": "Document\n", "id": "d1"}, context={})

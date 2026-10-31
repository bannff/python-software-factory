"""Promotion rejects cross-case Evals binding substitution before effects."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from factory.machine_learning.runtime.can_evaluation_policy import adequacy_bindings
from factory.machine_learning.runtime.can_lifecycle_refs import CanEvalsPointer
from factory.machine_learning.runtime.can_passport_operations import promote_passports
from factory.machine_learning.runtime.passport_store_models import ModelPassportRef

from .passport_fixtures import passport
from .test_can_case_binding_issuance import (
    _POINTER, _adequacy, _legacy, _response,
)


def test_cross_case_substitution_fails_before_effect_or_service(tmp_path: Path):
    pointer = CanEvalsPointer.model_validate(_POINTER)
    adequacy = _adequacy()
    response = _response()
    bindings = adequacy_bindings(
        pointer, "multi", adequacy, response["summary"],
    )
    candidate = passport(
        tmp_path, model_id="model-1", can_legacy_binding=_legacy("0x1"),
        evaluation_pointers=(pointer,), evaluation_adequacy=(bindings[0],),
    )
    forged = candidate.model_copy(update={"evaluation_adequacy": (bindings[1],)})
    ref = ModelPassportRef(
        model_id=candidate.model_id, model_version=candidate.model_version,
        passport_revision=1, uri=(tmp_path / "candidate.json").as_uri(),
        digest=candidate.passport_digest,
    )
    calls = {"effect": 0, "service": 0}

    class Context:
        def conformance_receipt(self, *_args):
            intent = SimpleNamespace(effect_id="e" * 64, unit="unused", inputs={})
            receipt = SimpleNamespace(output={
                "passport_ref": ref.model_dump(mode="json"),
                "conformance_evidence": {},
            })
            return intent, receipt

        def effect(self, *_args, **_kwargs):
            calls["effect"] += 1
            pytest.fail("cross-case substitution must fail before effect")

    class Service:
        def get(self, _ref):
            return forged

        def promote_lifecycle(self, *_args, **_kwargs):
            calls["service"] += 1
            pytest.fail("cross-case substitution must fail before publication")

    with pytest.raises(ValueError, match="changed candidate bindings"):
        promote_passports(
            Context(), conformance_receipt_refs=[{"receipt": "x"}],
            invoker=lambda *_args, **_kwargs: response, service=Service(),
        )
    assert calls == {"effect": 0, "service": 0}

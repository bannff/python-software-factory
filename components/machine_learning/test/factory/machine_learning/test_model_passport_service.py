"""Injected ModelPassport service port behavior."""
from __future__ import annotations

from pathlib import Path

from factory.machine_learning.runtime.passport_service import ModelPassportService
from factory.machine_learning.runtime.passport_store_models import (
    ModelPassportPublication, ModelPassportRef,
)

from .passport_fixtures import passport


def test_service_uses_injected_store_and_verifier_for_issuance_and_read(
    tmp_path: Path,
) -> None:
    value = passport(tmp_path)
    ref = ModelPassportRef(
        model_id=value.model_id, model_version=value.model_version,
        passport_revision=value.passport_revision,
        uri=(tmp_path / "passport.json").as_uri(), digest=value.passport_digest,
    )

    class Store:
        def __init__(self):
            self.published = []

        def publish(self, item):
            self.published.append(item)
            return ModelPassportPublication(status="published", ref=ref)

        def get(self, requested):
            assert requested == ref
            return value

        def get_by_model(self, model_id, model_version, revision):
            assert (model_id, model_version, revision) == ("model-1", "1", 1)
            return value

    class Verifier:
        def __init__(self):
            self.verified = []

        def verify(self, item):
            self.verified.append(item)

    store, verifier = Store(), Verifier()
    service = ModelPassportService(store=store, verifier=verifier)
    assert service.issue_candidate(value).ref == ref
    assert service.get(ref) == value
    assert service.get_by_model("model-1", "1", 1) == value
    assert store.published == [value]
    assert verifier.verified == [value, value, value]

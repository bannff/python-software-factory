"""Ports for immutable model-passport persistence."""
from __future__ import annotations

from typing import Protocol

from .model_passport import ConformanceEvidence, ModelPassport
from .passport_store_models import ModelPassportPublication, ModelPassportRef


class ModelPassportStorePort(Protocol):
    def publish(self, passport: ModelPassport) -> ModelPassportPublication: ...
    def get(self, ref: ModelPassportRef) -> ModelPassport: ...
    def get_by_model(
        self, model_id: str, model_version: str, passport_revision: int,
    ) -> ModelPassport: ...


class ModelPassportVerifierPort(Protocol):
    def verify(self, passport: ModelPassport) -> None: ...


class ModelPassportConformanceRunnerPort(Protocol):
    def run(
        self, candidate: ModelPassport, ref: ModelPassportRef, *,
        effect_id: str | None = None,
    ) -> ConformanceEvidence: ...


__all__ = [
    "ModelPassportConformanceRunnerPort", "ModelPassportStorePort",
    "ModelPassportVerifierPort",
]

"""Strict transport-neutral contracts for approved DBC artifacts and resolution."""
from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator

from .scenario_pack_models import FrozenModel, digest, text, token


class DbcArtifactProvenance(FrozenModel):
    source_url: str
    artifact_uri: str
    source_kind: Literal["approved_manifest", "explicit_local"]
    spdx_license: str
    retrieved_at: str
    sha256: str
    parser_name: str
    parser_version: str
    validation_status: Literal["approved", "validated"]

    @field_validator("source_url", "artifact_uri", "retrieved_at")
    @classmethod
    def _required(cls, value: str) -> str:
        return text(value, "DBC provenance field")

    @field_validator("spdx_license", "parser_name", "parser_version")
    @classmethod
    def _tokens(cls, value: str) -> str:
        return token(value, "DBC provenance token")

    @field_validator("sha256")
    @classmethod
    def _sha(cls, value: str) -> str:
        return digest(value, "DBC artifact")

    @model_validator(mode="after")
    def _schemes(self) -> "DbcArtifactProvenance":
        artifact = urlparse(self.artifact_uri)
        if artifact.scheme != "file":
            raise ValueError("DBC artifact_uri must be an immutable local file URI")
        source = urlparse(self.source_url)
        allowed = {"http", "https"} if self.source_kind == "approved_manifest" else {"file"}
        if source.scheme not in allowed:
            raise ValueError("DBC source_url scheme is incompatible with source_kind")
        if self.source_kind == "approved_manifest" and self.spdx_license == "NOASSERTION":
            raise ValueError("approved DBC artifacts require an SPDX license")
        return self


class VehicleAliases(FrozenModel):
    make: str = ""
    model: str = ""
    years: tuple[StrictInt, ...] = ()
    aliases: tuple[str, ...] = Field(min_length=1)

    @field_validator("aliases")
    @classmethod
    def _aliases(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted({text(value, "vehicle alias") for value in values}))
        if len(normalized) != len(values):
            raise ValueError("vehicle aliases must be unique")
        return normalized


class MessageFingerprint(FrozenModel):
    arbitration_id: int = Field(strict=True, ge=0, le=0x1FFFFFFF)
    dlc: int = Field(strict=True, ge=0, le=64)
    is_extended: StrictBool = False


class DbcCatalogEntry(FrozenModel):
    catalog_id: str
    version: str
    provenance: DbcArtifactProvenance
    vehicle: VehicleAliases
    message_fingerprints: tuple[MessageFingerprint, ...] = Field(min_length=1)

    @field_validator("catalog_id", "version")
    @classmethod
    def _ids(cls, value: str) -> str:
        return token(value, "DBC catalog identity")

    @field_validator("message_fingerprints")
    @classmethod
    def _fingerprints(
        cls, values: tuple[MessageFingerprint, ...],
    ) -> tuple[MessageFingerprint, ...]:
        ordered = tuple(sorted(values, key=lambda item: (
            item.arbitration_id, item.dlc, item.is_extended,
        )))
        if len(set(ordered)) != len(ordered):
            raise ValueError("DBC message fingerprints must be unique")
        return ordered


class DbcCandidateScore(FrozenModel):
    catalog_id: str
    version: str
    artifact_sha256: str
    score: int = Field(strict=True, ge=0)
    matched_aliases: tuple[str, ...] = ()
    matched_fingerprints: tuple[MessageFingerprint, ...] = ()
    explanation: tuple[str, ...] = ()


class DbcResolution(FrozenModel):
    status: Literal["resolved", "ambiguous", "not_found"]
    selected: DbcCatalogEntry | None = None
    candidates: tuple[DbcCandidateScore, ...] = ()
    threshold: int = Field(default=10, strict=True, ge=0)
    errors: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _shape(self) -> "DbcResolution":
        if (self.status == "resolved") != (self.selected is not None):
            raise ValueError("resolved DBC result must contain exactly one selection")
        return self

"""Canonical DBC definitions, semantic bindings, and decoded observations."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictBool, field_validator, model_validator

from .dbc_models import DbcArtifactProvenance
from .scenario_pack_models import FrozenModel, digest, text, token


class DbcSignalDefinition(FrozenModel):
    signal_id: str
    name: str
    start_bit: int = Field(strict=True, ge=0)
    length_bits: int = Field(strict=True, gt=0, le=64)
    byte_order: Literal["little_endian", "big_endian"]
    is_signed: bool
    scale: float
    offset: float
    minimum: float | None = None
    maximum: float | None = None
    unit: str = ""
    receivers: tuple[str, ...] = ()
    semantic_roles: tuple[str, ...] = ()

    @field_validator("signal_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return token(value, "DBC signal ID")

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return text(value, "DBC signal name")

    @model_validator(mode="after")
    def _bounds(self) -> "DbcSignalDefinition":
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("DBC signal minimum exceeds maximum")
        return self


class DbcMessageDefinition(FrozenModel):
    message_id: str
    name: str
    arbitration_id: int = Field(strict=True, ge=0, le=0x1FFFFFFF)
    is_extended: StrictBool
    dlc: int = Field(strict=True, ge=0, le=64)
    senders: tuple[str, ...] = ()
    signals: tuple[DbcSignalDefinition, ...] = ()

    @field_validator("message_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return token(value, "DBC message ID")

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return text(value, "DBC message name")


class DbcVersionDefinition(FrozenModel):
    definition_id: str
    catalog_id: str
    version: str
    digest: str
    provenance: DbcArtifactProvenance
    messages: tuple[DbcMessageDefinition, ...] = Field(min_length=1)

    @field_validator("definition_id", "catalog_id", "version")
    @classmethod
    def _ids(cls, value: str) -> str:
        return token(value, "DBC definition identity")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "DBC definition")


class SemanticRoleBinding(FrozenModel):
    role: str
    signal_id: str
    message_id: str
    signal_name: str
    unit: str = ""

    @field_validator("role", "signal_id", "message_id")
    @classmethod
    def _tokens(cls, value: str) -> str:
        return token(value, "semantic role binding")


class DecodedSignalObservation(FrozenModel):
    observation_id: str
    signal_id: str
    dbc_definition_id: str
    frame_id: str
    timestamp_ns: int = Field(strict=True, ge=0)
    value: float
    unit: str = ""

    @field_validator("observation_id", "signal_id", "dbc_definition_id", "frame_id")
    @classmethod
    def _tokens(cls, value: str) -> str:
        return token(value, "decoded signal observation identity")

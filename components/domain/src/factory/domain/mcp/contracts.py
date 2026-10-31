"""Strict DTOs for Domain's public MCP boundary."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Reject unknown and coerced public boundary values."""

    model_config = ConfigDict(extra="forbid", strict=True)


class ManifestInput(StrictModel):
    domain_id: str


class EmptyInput(StrictModel):
    pass


class OpenEngagementInput(ManifestInput):
    persona_id: str | None = None


class TypeDescriptorInput(StrictModel):
    label: str
    color: str = ""
    icon: str = ""
    description: str | None = None


class ThemeInput(StrictModel):
    primary: str = ""
    accent: str = ""
    severity_high: str = ""


class PresentationManifestInput(StrictModel):
    domain_id: str
    display_name: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
    taxonomy_ref: str | None = None
    type_descriptors: dict[str, TypeDescriptorInput] = Field(default_factory=dict)
    severity_palette: dict[str, str] = Field(default_factory=dict)
    artifact_renderers: dict[str, str] = Field(default_factory=dict)
    theme: ThemeInput | None = None
    default_persona_id: str | None = None
    version: str = "1"


class CreateManifestInput(StrictModel):
    manifest: PresentationManifestInput


class TypeDescriptorOutput(StrictModel):
    label: str
    color: str = ""
    icon: str = ""
    description: str | None = None


class ThemeOutput(StrictModel):
    primary: str = ""
    accent: str = ""
    severity_high: str = ""


class ManifestOutput(StrictModel):
    domain_id: str
    display_name: str = ""
    labels: dict[str, str]
    taxonomy_ref: str | None = None
    type_descriptors: dict[str, TypeDescriptorOutput]
    severity_palette: dict[str, str]
    artifact_renderers: dict[str, str]
    theme: ThemeOutput | None = None
    default_persona_id: str | None = None
    version: str = "1"


class EngagementOutput(StrictModel):
    id: str
    domain_id: str
    persona_id: str | None = None
    name: str = ""
    created_at: str


class GetManifestOutput(StrictModel):
    manifest: ManifestOutput


class ListManifestsOutput(StrictModel):
    manifests: list[ManifestOutput]
    count: int


class OpenEngagementOutput(StrictModel):
    engagement: EngagementOutput
    manifest: ManifestOutput
    persona_id: str | None = None


class ActiveEngagementOutput(StrictModel):
    active: bool
    engagement: EngagementOutput | None = None


class CloseEngagementOutput(StrictModel):
    ok: bool
    active: bool


class ManifestMutationOutput(StrictModel):
    ok: bool
    domain_id: str | None = None
    deleted: bool | None = None
    error: str | None = None


__all__ = [
    "ActiveEngagementOutput", "CloseEngagementOutput", "CreateManifestInput",
    "EmptyInput", "EngagementOutput", "GetManifestOutput", "ListManifestsOutput",
    "ManifestInput", "ManifestMutationOutput", "ManifestOutput", "OpenEngagementInput",
    "OpenEngagementOutput", "ThemeOutput", "TypeDescriptorOutput",
]

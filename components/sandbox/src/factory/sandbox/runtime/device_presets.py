"""Typed device targets layered over reusable Sandbox image profiles.

The resource envelope bounds a Linux container; it is not native device
emulation. Packaged presets take precedence over an optional user overlay.
"""
from __future__ import annotations

import hashlib
import json
import os
from importlib.resources import files
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..authoring import _assert_within_root
from .profile_store import assert_valid_profile_name

_DATA_PACKAGE = "factory.sandbox.runtime.device_presets_data"
_OVERLAY_ENV = "SANDBOX_DEVICE_PRESETS_DIR"
_LABEL_PREFIX = "factory.sandbox."


class ProxyEnvelope(BaseModel):
    """Linux Docker constraints used for an approximate device rehearsal."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    platform: Literal["linux/arm64", "linux/amd64"]
    cpus: float = Field(gt=0, allow_inf_nan=False)
    memory_mb: int = Field(ge=64)


class DevicePreset(BaseModel):
    """Device identity, evidence URL, and Linux proxy envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,127}$")
    vendor: str = Field(min_length=1)
    model: str = Field(min_length=1)
    variant: str | None = None
    form_factor: Literal["phone", "tablet", "rugged_handheld", "single_board"]
    os_family: Literal["ios", "ipados", "android", "linux"]
    fidelity: Literal["linux_proxy"]
    source_url: str
    proxy: ProxyEnvelope

    @field_validator("source_url")
    @classmethod
    def require_https_source(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("source_url must be an HTTPS URL with a hostname")
        return value

    @model_validator(mode="after")
    def check_device_taxonomy(self) -> "DevicePreset":
        allowed = {
            "ios": {"phone"},
            "ipados": {"tablet"},
            "android": {"phone", "tablet", "rugged_handheld"},
            "linux": {"single_board"},
        }
        if self.form_factor not in allowed[self.os_family]:
            raise ValueError(
                f"form_factor {self.form_factor!r} is incompatible with "
                f"os_family {self.os_family!r}"
            )
        return self


class DeviceRunLabels(BaseModel):
    """Validated, comma-free Docker labels for selected device runs."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    profile: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,127}$")
    device_preset: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,127}$")
    fidelity: Literal["linux_proxy"]
    platform: Literal["linux/arm64", "linux/amd64"]
    cpus: float = Field(gt=0, allow_inf_nan=False)
    memory_mb: int = Field(ge=64)
    preset_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    def docker_labels(self) -> dict[str, str]:
        return {
            f"{_LABEL_PREFIX}{key}": str(value)
            for key, value in self.model_dump(exclude_none=True).items()
        }

    @classmethod
    def from_docker_labels(cls, labels: dict[str, str]) -> "DeviceRunLabels":
        values = {
            field: labels[f"{_LABEL_PREFIX}{field}"]
            for field in cls.model_fields
            if f"{_LABEL_PREFIX}{field}" in labels
        }
        values["cpus"] = float(values["cpus"])
        values["memory_mb"] = int(values["memory_mb"])
        return cls.model_validate(values)


def preset_sha256(preset: DevicePreset) -> str:
    """Stable content identity for a resolved preset at launch time."""
    canonical = json.dumps(
        preset.model_dump(mode="json"), sort_keys=True,
        separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_preset(name: str, content: str) -> DevicePreset:
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed device preset YAML: {name}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Device preset {name!r} must be a YAML mapping")
    data.setdefault("name", name)
    if data["name"] != name:
        raise ValueError(f"Device preset name must match filename: {name}")
    return DevicePreset.model_validate(data)


def _packaged_names() -> list[str]:
    return sorted(
        entry.name[:-5]
        for entry in files(_DATA_PACKAGE).iterdir()
        if entry.name.endswith(".yaml") and entry.is_file()
    )


def _overlay_root() -> Path | None:
    configured = os.environ.get(_OVERLAY_ENV)
    return Path(configured) if configured else None


def list_device_presets() -> list[str]:
    """List packaged and user names; packaged entries win collisions."""
    names = set(_packaged_names())
    root = _overlay_root()
    if root is not None and root.is_dir():
        for path in root.glob("*.yaml"):
            try:
                assert_valid_profile_name(path.stem)
            except ValueError:
                continue
            names.add(path.stem)
    return sorted(names)


def resolve_device_preset(name: str) -> DevicePreset:
    """Resolve a safe preset name from the packaged catalog or overlay."""
    assert_valid_profile_name(name)
    packaged = files(_DATA_PACKAGE).joinpath(f"{name}.yaml")
    if packaged.is_file():
        return _parse_preset(name, packaged.read_text(encoding="utf-8"))
    root = _overlay_root()
    if root is not None:
        path = root / f"{name}.yaml"
        _assert_within_root(root, path)
        if path.is_file():
            return _parse_preset(name, path.read_text(encoding="utf-8"))
    raise ValueError(f"Unknown device preset: {name}")

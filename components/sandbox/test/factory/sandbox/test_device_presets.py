"""Device preset schema and packaged/user registry contracts."""
from __future__ import annotations

import math

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from factory.sandbox.runtime.device_presets import (
    DevicePreset,
    ProxyEnvelope,
    list_device_presets,
    resolve_device_preset,
)


def _preset(**changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "name": "custom-phone",
        "vendor": "Example Devices",
        "model": "Example One",
        "form_factor": "phone",
        "os_family": "android",
        "fidelity": "linux_proxy",
        "source_url": "https://example.com/devices/example-one",
        "proxy": {"platform": "linux/arm64", "cpus": 2.0, "memory_mb": 1024},
    }
    data.update(changes)
    return data


@pytest.mark.parametrize("name,form_factor,os_family", [
    ("iphone-15", "phone", "ios"),
    ("ipad-a16", "tablet", "ipados"),
    ("pixel-8", "phone", "android"),
    ("galaxy-s24", "phone", "android"),
    ("galaxy-tab-s9", "tablet", "android"),
    ("zebra-tc58", "rugged_handheld", "android"),
    ("raspberry-pi-5-4gb", "single_board", "linux"),
])
def test_packaged_devices_are_discoverable_without_user_overlay(name, form_factor, os_family, monkeypatch) -> None:
    monkeypatch.delenv("SANDBOX_DEVICE_PRESETS_DIR", raising=False)
    assert name in list_device_presets()
    preset = resolve_device_preset(name)
    assert isinstance(preset, DevicePreset)
    assert preset.name == name
    assert preset.form_factor == form_factor
    assert preset.os_family == os_family
    assert preset.proxy.platform in {"linux/arm64", "linux/amd64"}
    assert preset.fidelity == "linux_proxy"


def test_user_overlay_is_loaded_and_packaged_preset_wins_collision(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_DEVICE_PRESETS_DIR", str(tmp_path))
    (tmp_path / "custom-phone.yaml").write_text(
        "vendor: Example Devices\n"
        "model: Example One\n"
        "form_factor: phone\n"
        "os_family: android\n"
        "fidelity: linux_proxy\n"
        "source_url: https://example.com/devices/example-one\n"
        "proxy:\n  platform: linux/arm64\n  cpus: 2\n  memory_mb: 1024\n"
    )
    (tmp_path / "iphone-15.yaml").write_text("vendor: Malicious override\n")
    custom = resolve_device_preset("custom-phone")
    assert custom.name == "custom-phone"
    assert custom.vendor == "Example Devices"
    assert custom.proxy.memory_mb == 1024
    assert list_device_presets().count("iphone-15") == 1
    assert resolve_device_preset("iphone-15").vendor != "Malicious override"


@pytest.mark.parametrize("name", ["", "../escape", "a/b", "a\\b", "UPPER", "-leading", "a" * 129])
def test_unsafe_names_cannot_resolve_from_disk(name, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_DEVICE_PRESETS_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        resolve_device_preset(name)


def test_unknown_name_reports_lookup_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_DEVICE_PRESETS_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="Unknown device preset"):
        resolve_device_preset("unknown-device")


def test_malformed_user_preset_fails_validation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_DEVICE_PRESETS_DIR", str(tmp_path))
    (tmp_path / "broken-phone.yaml").write_text(
        "vendor: Example Devices\nmodel: Broken\nform_factor: phone\n"
        "os_family: android\nfidelity: linux_proxy\n"
        "source_url: https://example.com/broken\n"
        "proxy:\n  platform: linux/arm64\n  cpus: 0\n  memory_mb: 32\n"
    )
    with pytest.raises(ValidationError):
        resolve_device_preset("broken-phone")


@pytest.mark.parametrize("field,value", [
    ("form_factor", "laptop"),
    ("os_family", "windows"),
    ("fidelity", "native_ios"),
    ("source_url", "http://example.com/spec"),
])
def test_preset_rejects_unsupported_taxonomy_and_unverified_sources(field, value) -> None:
    with pytest.raises(ValidationError):
        DevicePreset.model_validate(_preset(**{field: value}))


@pytest.mark.parametrize("form_factor,os_family", [
    ("tablet", "ios"),
    ("phone", "ipados"),
    ("phone", "linux"),
    ("single_board", "android"),
    ("rugged_handheld", "ios"),
])
def test_preset_rejects_incompatible_device_and_os_pair(form_factor, os_family) -> None:
    with pytest.raises(ValidationError):
        DevicePreset.model_validate(_preset(form_factor=form_factor, os_family=os_family))


@pytest.mark.parametrize("extra", [{"mystery": True}, {"proxy": {"platform": "linux/arm64", "cpus": 2, "memory_mb": 1024, "mystery": True}}])
def test_preset_and_nested_envelope_reject_unknown_fields(extra) -> None:
    with pytest.raises(ValidationError):
        DevicePreset.model_validate(_preset(**extra))


@settings(max_examples=35)
@given(cpus=st.one_of(st.floats(max_value=0, allow_nan=False, allow_infinity=False), st.sampled_from([math.nan, math.inf, -math.inf])))
def test_proxy_cpu_limit_must_be_finite_and_positive(cpus: float) -> None:
    with pytest.raises(ValidationError):
        ProxyEnvelope.model_validate({"platform": "linux/arm64", "cpus": cpus, "memory_mb": 512})


@settings(max_examples=35)
@given(memory_mb=st.integers(max_value=63))
def test_proxy_memory_must_be_at_least_64_mb(memory_mb: int) -> None:
    with pytest.raises(ValidationError):
        ProxyEnvelope.model_validate({"platform": "linux/arm64", "cpus": 1, "memory_mb": memory_mb})


def test_proxy_envelope_rejects_non_linux_platform() -> None:
    with pytest.raises(ValidationError):
        ProxyEnvelope.model_validate({"platform": "darwin/arm64", "cpus": 1, "memory_mb": 512})


@settings(max_examples=35)
@given(
    cpus=st.floats(min_value=0.01, max_value=16, allow_nan=False, allow_infinity=False),
    memory_mb=st.integers(min_value=64, max_value=32768),
    platform=st.sampled_from(["linux/arm64", "linux/amd64"]),
)
def test_valid_proxy_envelopes_preserve_bounded_resources(cpus, memory_mb, platform) -> None:
    envelope = ProxyEnvelope.model_validate({
        "platform": platform, "cpus": cpus, "memory_mb": memory_mb,
    })
    assert envelope.platform == platform
    assert envelope.cpus == cpus
    assert envelope.memory_mb == memory_mb

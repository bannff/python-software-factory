"""Polylith interface for arcade_config brick."""

from .core import ArcadeConfig, SystemCoreMapping
from .runtime.models import (
    RETROPAD_BUTTONS,
    CoreOption,
    InputRemap,
    RawOption,
    RunAheadConfig,
    Scope,
    ShaderPreset,
)
from .runtime.resolver import override_path
from .runtime.serializers import (
    parse_cfg,
    serialize_cfg,
    serialize_core_options,
    serialize_remap,
    serialize_shader_ref,
)
from .runtime.settings import RetroArchRuntimeSettings, resolve_runtime_settings
from .runtime.core_options import build_core_options
from .runtime.input_remaps import build_input_remaps, RETROPAD_BUTTON_ORDER
from .runtime.schemas import CORE_OPTION_SCHEMAS, SHADER_PRESETS
from .runtime.writer import write_config

__all__ = [
    "ArcadeConfig",
    "CORE_OPTION_SCHEMAS",
    "CoreOption",
    "InputRemap",
    "RETROPAD_BUTTONS",
    "RETROPAD_BUTTON_ORDER",
    "RawOption",
    "RetroArchRuntimeSettings",
    "RunAheadConfig",
    "SHADER_PRESETS",
    "Scope",
    "ShaderPreset",
    "SystemCoreMapping",
    "build_core_options",
    "build_input_remaps",
    "override_path",
    "parse_cfg",
    "resolve_runtime_settings",
    "serialize_cfg",
    "serialize_core_options",
    "serialize_remap",
    "serialize_shader_ref",
    "write_config",
]

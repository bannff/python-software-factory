"""Build the configured native MCP-v2 process surface."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from factory.mcp_utils.interface import (
    NativeMCPV2Composer,
    NativeToolRegistration,
    ServerCompositionPlan,
    ServerSurfaceIdentity,
)

from .selected_tools import native_registrations, resolve_selected_tools


def build_configured_native_server(
    aggregator: Any,
    *,
    server_name: str,
    discovery_mode: Literal["progressive", "flat"],
    allowlist: set[str] | None = None,
    access_controller: Any | None = None,
) -> tuple[Any, ServerCompositionPlan]:
    """Compose progressive meta-only or flat admitted-tool-only surfaces."""
    if discovery_mode not in {"progressive", "flat"}:
        raise ValueError("discovery_mode must be 'progressive' or 'flat'")
    if discovery_mode == "progressive":
        registrations = list(_meta_registrations(aggregator))
    else:
        selected = resolve_selected_tools(
            aggregator, allowlist, rename_dot_to_underscore=True,
        )
        registrations = list(native_registrations(selected))
    registrations_tuple = tuple(registrations)
    names = frozenset(item.name for item in registrations_tuple)
    identity = ServerSurfaceIdentity(
        entry_point="factory.mcp_server.core:main",
        route_bindings=("/mcp",),
        transport_bindings=("in_process", "http", "stdio"),
        process_lifecycle_id=server_name,
        catalog_digest=_digest(sorted(names)),
        scope_digest=_digest(sorted(allowlist) if allowlist is not None else ["*"]),
        policy_digest=_digest(["typed-v2", "service-policy", "public-admission"]),
        closure_digest=_digest(["mcp==2.1.1", "native-tool-catalog"]),
    )
    plan = ServerCompositionPlan(identity, discovery_mode, names)
    composer = (
        NativeMCPV2Composer(plan, registrations_tuple)
        if access_controller is None
        else NativeMCPV2Composer(
            plan, registrations_tuple, access_controller=access_controller,
        )
    )
    return composer.compose(), plan


def _meta_registrations(aggregator: Any) -> tuple[NativeToolRegistration, ...]:
    from .native_meta import build_native_meta_catalog

    result = []
    for tool in build_native_meta_catalog(aggregator).tool_map().values():
        excluded = frozenset({"arguments"}) if tool.name == "call_brick_tool" else frozenset()
        envelope_excluded = frozenset({"envelope"}) if tool.name == "call_brick_tool" else frozenset()
        result.append(NativeToolRegistration(
            tool.name, tool.description, tool.fn,
            brick_name="mcp_server", source_name=tool.name,
            telemetry_excluded_argument_fields=excluded,
            telemetry_excluded_envelope_fields=envelope_excluded,
        ))
    return tuple(result)


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["build_configured_native_server"]

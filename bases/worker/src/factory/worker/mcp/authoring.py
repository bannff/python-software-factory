"""Typed, security-gated authoring tools for the Worker base."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, authoring
from factory.mcp_utils.registration import typed_tool

from .contracts.authoring import (
    AuthoringStatusOutput,
    SetConfigInput,
    SetConfigOutput,
    SwitchBackendInput,
    SwitchBackendOutput,
)
from .contracts.base import EmptyInput

if TYPE_CHECKING:
    from ..runtime.runtime import WorkerRuntime


def register(
    mcp: Any,
    get_runtime: Callable[[], "WorkerRuntime"],
    authoring_enabled: bool = False,
) -> None:
    """Register authoring tools; disabled mode remains discoverable and typed."""

    @typed_tool(mcp, name="worker.authoring.get_status")
    @authoring(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def authoring_get_status() -> ToolResult[AuthoringStatusOutput]:
        """Return the Worker authoring gate and backend catalog."""
        runtime = get_runtime()
        return {
            "enabled": authoring_enabled,
            "available_backends": runtime.available_backends(),
            "current_backend": runtime.backend_name,
        }

    @typed_tool(mcp, name="worker.authoring.switch_backend")
    @authoring(input_model=SwitchBackendInput, output_model=SwitchBackendOutput)
    def authoring_switch_backend(
        backend: str,
        broker_url: str | None = None,
    ) -> ToolResult[SwitchBackendOutput]:
        """Switch to a supported backend through WorkerRuntime's public API."""
        runtime = get_runtime()
        available = runtime.available_backends()
        if not authoring_enabled:
            return {
                "switched": False,
                "backend": None,
                "requested": backend,
                "available": available,
                "error": "authoring_disabled",
            }
        result = runtime.switch_backend(backend, broker_url=broker_url)
        return {
            "switched": bool(result.get("switched")),
            "backend": result.get("backend"),
            "requested": backend,
            "available": available,
            "error": result.get("error"),
        }

    @typed_tool(mcp, name="worker.authoring.set_config")
    @authoring(input_model=SetConfigInput, output_model=SetConfigOutput)
    def authoring_set_config(
        queues: list[str] | None = None,
        concurrency: int | None = None,
    ) -> ToolResult[SetConfigOutput]:
        """Apply supported configuration and report unsupported settings exactly."""
        runtime = get_runtime()
        if not authoring_enabled:
            return {
                "updated": False,
                "changes": {},
                "unsupported": [],
                "error": "authoring_disabled",
            }
        result = runtime.update_config(queues=queues, concurrency=concurrency)
        return {
            "updated": bool(result.get("updated")),
            "changes": result.get("changes", {}),
            "unsupported": result.get("unsupported", []),
            "error": result.get("error"),
        }


__all__ = ["register"]

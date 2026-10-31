"""Typed deterministic contract MCP tools for the Sandbox brick."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from factory.mcp_utils.interface import deterministic, ok
from factory.mcp_utils.runtime.tool_result import ToolResult
from .contracts import EmptyInput
from .deterministic_models import (
    CapabilitiesResult, ConfigSchemaResult, DevicePresetInfo, DevicePresetsResult,
    HealthResult, LiveLaunchInfo, LiveLaunchesResult, ProfileInfo, ProfilesResult,
)
from ..core import COMPONENT_NAME, COMPONENT_VERSION
if TYPE_CHECKING:
    from ..runtime.runtime import SandboxRuntime

def register(mcp: Any, runtime: "SandboxRuntime") -> None:
    """Register typed deterministic contract tools."""

    @mcp.tool(name="sandbox.get_capabilities")
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesResult)
    def get_capabilities() -> ToolResult[CapabilitiesResult]:
        """Return machine-readable Sandbox capabilities."""
        return ok(CapabilitiesResult(
            name=COMPONENT_NAME, version=COMPONENT_VERSION,
            tools={
                "deterministic": [
                    "sandbox.get_capabilities", "sandbox.health_check",
                    "sandbox.describe_config_schema", "sandbox.list_profiles",
                    "sandbox.list_device_presets",
                    "sandbox.list_environments", "sandbox.generate_cfn_from_recon",
                    "sandbox.validate_manifest", "sandbox.list_live_launch_ids",
                    "sandbox_get_dashboard_summary",
                    "sandbox_get_environment_activity",
                    "sandbox_get_environment_graph_context", "sandbox_get_views",
                ],
                "operational": [
                    "sandbox.provision", "sandbox.terminate", "sandbox.get_status",
                    "sandbox.execute", "sandbox.upload_file", "sandbox.download_file",
                    "sandbox.apply_service_mocks", "sandbox.workspace_dir",
                    "sandbox.write_file", "sandbox.diff",
                    "sandbox.deploy_cfn", "sandbox.list_stacks", "sandbox.describe_stack",
                    "sandbox.delete_stack", "sandbox.translate_cfn", "sandbox.plan_provision",
                    "sandbox.apply_provision",
                ],
                "authoring": [
                    "sandbox.authoring.get_status", "sandbox.authoring.list_templates",
                    "sandbox.authoring.upsert_template", "sandbox.authoring.delete_template",
                ],
            },
            adapters=["aws_ec2", "aws_ssm", "mock"],
            features=[
                "environment_provisioning", "command_execution", "file_transfer",
                "session_management", "cfn_deployment", "manifest_provisioning",
            ],
        ))

    @mcp.tool(name="sandbox.health_check")
    @deterministic(input_model=EmptyInput, output_model=HealthResult)
    def health_check() -> ToolResult[HealthResult]:
        """Return Sandbox readiness and adapter health."""
        return ok(HealthResult.model_validate(runtime.health_check()))

    @mcp.tool(name="sandbox.describe_config_schema")
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaResult)
    def describe_config_schema() -> ToolResult[ConfigSchemaResult]:
        """Describe supported Sandbox configuration fields."""
        return ok(ConfigSchemaResult(type="object", properties={
            "instance_type": {"type": "string", "default": "t3.micro"},
            "timeout_seconds": {"type": "integer", "default": 3600},
            "auto_terminate": {"type": "boolean", "default": True},
            "ami_id": {"type": "string", "nullable": True},
            "security_group_id": {"type": "string", "nullable": True},
            "subnet_id": {"type": "string", "nullable": True},
        }))

    @mcp.tool(name="sandbox.list_profiles")
    @deterministic(input_model=EmptyInput, output_model=ProfilesResult)
    def list_profiles() -> ToolResult[ProfilesResult]:
        """List all provisionable target profiles (built-in + user YAML).

        Reads the runtime's merged view so user-defined profiles under
        SANDBOX_PROFILES_DIR are discoverable, not just code built-ins. A
        malformed user profile is skipped (best-effort), never failing the list.
        """
        from ..runtime.profiles import list_profiles as _profile_names, resolve_profile
        profiles: dict[str, ProfileInfo] = {}
        for name in _profile_names():
            try:
                profile = resolve_profile(name)
            except Exception:  # noqa: BLE001 - one bad user YAML must not hide the rest
                continue
            profiles[name] = ProfileInfo(
                image=profile.image, ports=profile.ports,
                health_check_url=profile.health_check_url,
                platform=profile.platform, cpus=profile.cpus,
                memory_mb=profile.memory_mb,
                device_target=(
                    profile.device_target.model_dump() if profile.device_target else None
                ),
            )
        return ok(ProfilesResult(profiles=profiles))

    @mcp.tool(name="sandbox.list_device_presets")
    @deterministic(input_model=EmptyInput, output_model=DevicePresetsResult)
    def list_device_presets() -> ToolResult[DevicePresetsResult]:
        """List validated device targets and their Linux proxy envelopes."""
        from ..runtime.device_presets import (
            list_device_presets as _names,
            resolve_device_preset,
        )

        presets: dict[str, DevicePresetInfo] = {}
        for name in _names():
            try:
                presets[name] = DevicePresetInfo.model_validate(
                    resolve_device_preset(name).model_dump()
                )
            except (ValueError, OSError, KeyError):
                # An invalid user YAML must not hide the rest of the catalog.
                continue
        return ok(DevicePresetsResult(presets=presets))

    @mcp.tool(name="sandbox.list_live_launch_ids")
    @deterministic(input_model=EmptyInput, output_model=LiveLaunchesResult)
    def list_live_launch_ids() -> ToolResult[LiveLaunchesResult]:
        """List live workload launches (``factory.workload``-labeled containers).

        Reports the live workload set for Workflow's reconciliation diff.
        Sandbox only reports liveness; it never revokes credentials or decides
        revocation.
        """
        from ..runtime.discovery import discover_live_workloads
        return ok(LiveLaunchesResult(launches=[
            LiveLaunchInfo(**workload) for workload in discover_live_workloads()
        ]))

"""Provisioning business logic — validate, plan, apply.

Extracted from SandboxRuntime to keep runtime.py under 200 LOC.
All functions receive dependencies as arguments (no global state).
"""
from __future__ import annotations

from typing import Any, Callable, Awaitable

from .manifest import ProvisionPlan, SandboxManifest
from .adapters.cfn_provisioner import CfnProvisioner, _STORE_TYPE_MAP, _COMPUTE_TYPE_MAP

# Compute types handled by ComposeProvisioner
COMPOSE_COMPUTE_TYPES = ("java_server", "container")


async def validate_manifest(manifest_data: dict[str, Any]) -> dict[str, Any]:
    """Validate a SandboxManifest dict. Returns validation result."""
    errors: list[str] = []
    try:
        m = SandboxManifest.model_validate(manifest_data)
    except Exception as e:
        return {"valid": False, "errors": [str(e)]}
    if not m.app_name:
        errors.append("app_name is required")
    if not m.data_stores and not m.compute and not m.cfn_template:
        errors.append(
            "Manifest must have at least one of: "
            "data_stores, compute, or cfn_template"
        )
    for ds in m.data_stores:
        if ds.type not in _STORE_TYPE_MAP:
            errors.append(f"Unsupported data store type '{ds.type}'")
    for c in m.compute:
        if c.type not in _COMPUTE_TYPE_MAP and c.type not in COMPOSE_COMPUTE_TYPES:
            errors.append(f"Unknown compute type '{c.type}'")
    if errors:
        return {"valid": False, "errors": errors}
    return {
        "valid": True, "errors": [],
        "manifest": m.model_dump(),
        "summary": {
            "app_name": m.app_name,
            "data_stores": len(m.data_stores),
            "compute": len(m.compute),
            "service_deps": len(m.service_deps),
            "init_scripts": len(m.init_scripts),
            "has_cfn_template": m.cfn_template is not None,
        },
    }


async def plan_provision(manifest_data: dict[str, Any]) -> dict[str, Any]:
    """Generate a ProvisionPlan from a manifest dict."""
    m = SandboxManifest.model_validate(manifest_data)
    provisioner = CfnProvisioner()
    plan = await provisioner.plan(m)
    return plan.model_dump()


async def apply_provision(
    env_id: str,
    plan_data: dict[str, Any],
    execute_fn: Callable[..., Awaitable[Any]],
) -> dict[str, Any]:
    """Apply a ProvisionPlan to a sandbox environment."""
    p = ProvisionPlan.model_validate(plan_data)
    provisioner = CfnProvisioner()
    result = await provisioner.apply(env_id, p, execute_fn)
    return result.model_dump()

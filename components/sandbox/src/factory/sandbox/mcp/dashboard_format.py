"""Pure row/format helpers for the sandbox dashboard summary.

Age formatting, health/status mapping, profile resolution, and the environment
+ profile row builders. Everything here is a pure function of its inputs (no
runtime or invoker access), which keeps it trivially testable and shared by
the orchestrator and the activity/graph readers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_STATUS_ORDER = ["running", "provisioning", "pending", "unknown", "terminated", "error"]


def sandbox_entity_id(env_id: str) -> str:
    """Return the canonical graph entity id for a sandbox environment."""
    return f"sandbox-env-{env_id}"


def age_minutes(created_at: str) -> int:
    """Whole minutes since ``created_at`` (ISO 8601); ``0`` when unparseable."""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 60))
    except ValueError:
        return 0


def age_label(minutes: int) -> str:
    """Render an age in minutes as a compact ``just now``/``5m``/``2h``/``3d``."""
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"


def health_state(status: str) -> str:
    """Map an environment status to a coarse health state token."""
    if status == "running":
        return "healthy"
    if status in {"provisioning", "pending"}:
        return "warming"
    if status in {"terminated"}:
        return "inactive"
    if status in {"error", "unknown"}:
        return "error"
    return "inactive"


def adapter_name(health: dict[str, Any]) -> str:
    """Extract the adapter name from a runtime health report."""
    adapter = health.get("adapter")
    if isinstance(adapter, dict):
        return str(adapter.get("adapter", "unknown"))
    return str(adapter or "unknown")


def status_rank(status: str) -> int:
    """Sort key placing problem states first and terminated last."""
    order = {
        "error": 0,
        "unknown": 1,
        "provisioning": 2,
        "pending": 3,
        "running": 4,
        "terminated": 5,
    }
    return order.get(status, 99)


def profile_name(env: dict[str, Any], metadata: dict[str, Any], profiles: dict[str, Any]) -> str:
    """Resolve the profile for an environment from metadata or its env_id."""
    explicit = metadata.get("profile")
    if isinstance(explicit, str) and explicit:
        return explicit
    env_id = str(env.get("env_id", "")).lower()
    for name in profiles:
        if name in env_id:
            return name
    return ""


def environment_row(env: dict[str, Any], profiles: dict[str, Any]) -> dict[str, Any]:
    """Build a dashboard environment row from a raw environment dict."""
    status = str(env.get("status", "unknown"))
    metadata = env.get("metadata") if isinstance(env.get("metadata"), dict) else {}
    resolved_profile = profile_name(env, metadata, profiles)
    profile = profiles.get(resolved_profile) if resolved_profile else None
    ports_map = metadata.get("ports") if isinstance(metadata.get("ports"), dict) else {}
    ports = [f"{host}->{container}" for host, container in ports_map.items()]
    if not ports and profile is not None:
        ports = [f"{host}->{container}" for host, container in profile.ports.items()]

    minutes = age_minutes(str(env.get("created_at", "")))
    return {
        **env,
        "status": status,
        "profile_name": resolved_profile or "ad_hoc",
        "profile_health_url": metadata.get("health_check_url") or (profile.health_check_url if profile else ""),
        "ports": ports,
        "endpoint_count": len(ports),
        "age_minutes": minutes,
        "age_label": age_label(minutes),
        "health_state": health_state(status),
        "workspace_hint": f"/tmp/factory-sandbox/{env.get('env_id', '')}/artifacts",
    }


def profile_row(name: str, profile: Any, env_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a dashboard profile row with its active-environment count."""
    ports = [f"{host}->{container}" for host, container in profile.ports.items()]
    return {
        "name": name,
        "image": profile.image,
        "health_check_url": profile.health_check_url or "",
        "container_name": profile.container_name,
        "shell": profile.shell,
        "ports": ports,
        "port_count": len(ports),
        "health_timeout": profile.health_check_timeout,
        "active_count": sum(1 for item in env_rows if item.get("profile_name") == name),
    }

"""Target profile extraction from graph for experiment reports.

Migrated off f-string Cypher (bd python-factory-ky0i) onto
``graph_graph_get_target_app`` shipped in bd python-factory-j1lb. The
typed singleton lookup matches by ``app`` or ``name`` and prefers nodes
whose ``last_recon_run_id`` matches the run, mirroring the previous
``ORDER BY n.created_at DESC LIMIT 1`` semantics.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _typed_target(invoker: Any, target_app: str, run_id: str) -> dict:
    """Look up a TargetApp via the typed graph tool. Returns properties dict."""
    try:
        r = invoker(
            "graph_graph_get_target_app",
            target_app=target_app, run_id=run_id,
        )
    except Exception as e:
        logger.warning("graph_get_target_app failed: %s", e)
        return {}
    if not r or not r.ok or r.data is None or not r.data.found or r.data.entity is None:
        return {}
    return dict(r.data.entity.properties)


def build_target_profile(invoker: Any, target_app: str, run_id: str) -> dict[str, Any]:
    """Query TargetApp from graph, return target_profile section."""
    node = _typed_target(invoker, target_app, run_id)
    if not node:
        return _empty_profile(target_app)
    return {
        "app_name": node.get("name", target_app),
        "app_type": node.get("app_type", "web_application"),
        "tech_stack": _parse_list(node.get("tech_stack", "")),
        "framework": node.get("framework", ""),
        "security_level": node.get("security_level", "unknown"),
        "auth_mechanism": node.get("auth_mechanism", "unknown"),
        "ports": _parse_list(node.get("ports", "")),
        "endpoints_total": node.get("endpoints_total", 0),
        "attack_surface_summary": node.get("attack_surface_summary", ""),
        "threat_categories": _parse_list(node.get("threat_categories", "")),
        "last_recon_run_id": node.get("last_recon_run_id", run_id),
    }


def _parse_list(val: Any) -> list[str]:
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val:
        return [v.strip() for v in val.split(",") if v.strip()]
    return []


def _empty_profile(app: str) -> dict[str, Any]:
    return {
        "app_name": app, "app_type": "unknown", "tech_stack": [],
        "framework": "", "security_level": "unknown",
        "auth_mechanism": "unknown", "ports": [],
        "endpoints_total": 0, "attack_surface_summary": "",
        "threat_categories": [], "last_recon_run_id": "",
    }

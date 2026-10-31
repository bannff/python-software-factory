"""Security-domain verifier — DATA for the generic oracle registry.

This is the security PACK's contribution to the domain-agnostic
verification oracle (bd python-factory-216ti Contract B). It proves a
domain verifier is expressible as pure pack data with NO engine coupling:

- It re-runs the pentest purely by MCP tool-name indirection — calling
  ``security_pentest_scan`` (aggregated ``security_security_pentest_scan``)
  by name through the shared ``tool_invoker``. The pre-built pentest
  pipeline ``spawn_registered_graph`` is the heavier-weight alternative,
  also referenced by name.
- It imports NOTHING from ``factory.security`` internals and never
  imports the oracle engine — it registers through the oracle's public
  interface seam.

It maps a reproduced exploit signal to ``verified`` and a clean re-run to
``refuted``; an unavailable invoker leaves the finding ``verifying``.
"""

from __future__ import annotations

from typing import Any

# MCP tool names called BY NAME (no imports). The aggregator double-
# prefixes brick tools: ``security`` brick + ``security_pentest_scan``.
_PENTEST_TOOL = "security_security_pentest_scan"
_PENTEST_GRAPH = "spawn_registered_graph"  # pre-built pentest pipeline (by name)

_PROVEN_STATUSES = frozenset({"vulnerable", "exploited", "confirmed"})


def _invoker() -> Any | None:
    """Return the cross-brick MCP tool invoker, or None if unavailable."""
    try:
        from factory.mcp_utils.interface import get_service
        return get_service("tool_invoker")
    except Exception:
        return None


def _is_proven(result: Any) -> bool:
    """True when the re-run scan reproduces an exploitable signal."""
    if not isinstance(result, dict):
        return False
    if result.get("findings"):
        return True
    return str(result.get("status", "")).lower() in _PROVEN_STATUSES


class SecurityPentestVerifier:
    """Re-runs a pentest scan and maps the outcome to a neutral state."""

    name = "security-pentest"

    def verify(
        self, finding: dict[str, Any], context: dict[str, Any],
    ) -> dict[str, Any]:
        """Re-run the pentest by tool-name indirection; map to state."""
        invoke = _invoker()
        target = (
            context.get("target")
            or finding.get("location")
            or finding.get("affected_resource_arn")
            or ""
        )
        scan_type = context.get("scan_type", "vuln_scan")
        if invoke is None or not target:
            return {
                "state": "verifying",
                "evidence": "pentest unavailable; left in verifying",
                "verifier": self.name,
            }
        try:
            result = invoke(_PENTEST_TOOL, scan_type=scan_type, target=target)
        except Exception as exc:
            return {
                "state": "verifying",
                "evidence": f"pentest error: {exc}",
                "verifier": self.name,
            }
        proven = _is_proven(result)
        return {
            "state": "verified" if proven else "refuted",
            "evidence": {
                "tool": _PENTEST_TOOL,
                "scan_type": scan_type,
                "target": target,
                "result": result,
            },
            "verifier": self.name,
        }


def register_security_verifier(domain_id: str = "security") -> bool:
    """Register the security verifier into the oracle registry by domain.

    Uses the oracle's PUBLIC interface seam — no oracle-engine import.
    Returns False (never raises) if the oracle brick is unavailable.
    """
    try:
        from factory.oracle.interface import register_verifier
    except Exception:
        return False
    register_verifier(domain_id, SecurityPentestVerifier())
    return True


__all__ = ["SecurityPentestVerifier", "register_security_verifier"]

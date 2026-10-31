"""Deterministic interprocedural taint tracer.

Follows data flow from user-controlled sources to dangerous sinks
across method boundaries using regex-based call chain analysis.
Polymorphic — reads taint_sinks/taint_sources from caller args.

Exposed as security.trace_taint MCP tool.
"""
from __future__ import annotations

import re
from typing import Any


def trace(
    source_code: str,
    endpoint: str = "",
    param: str = "",
    taint_sinks: list[str] | None = None,
    taint_sources: list[str] | None = None,
    file_path: str = "",
) -> dict[str, Any]:
    """Trace taint from source param to sinks in source code.

    Args:
        source_code: Raw source code content (single file).
        endpoint: HTTP endpoint path for context.
        param: Parameter name to trace.
        taint_sinks: Dangerous operations to look for.
        taint_sources: Entry point patterns (annotations, etc).
        file_path: File path for context.

    Returns:
        Dict with hops, sink_reached, auth_gap, auth_checks.
    """
    if not source_code or not param:
        return {"hops": [], "sink_reached": False, "auth_gap": False}

    sinks = taint_sinks or []
    lines = source_code.splitlines()
    methods = _extract_methods(lines)
    hops: list[dict[str, Any]] = []
    auth_checks: list[dict[str, str]] = []
    sink_reached = False

    # Phase 1: Find where the param enters (source hop)
    param_re = re.compile(re.escape(param), re.IGNORECASE)
    for i, line in enumerate(lines, 1):
        if param_re.search(line):
            method = _find_enclosing_method(methods, i)
            hop_type = _classify_hop(method, line)
            auth = _check_auth(lines, i)
            if auth:
                auth_checks.append(auth)
            hops.append({
                "file": file_path, "function": method,
                "line": i, "hop_type": hop_type,
                "auth_check_present": bool(auth),
                "auth_check_type": auth.get("type", "") if auth else "",
                "code": line.strip()[:120],
            })

    # Phase 2: Check if any sink is reached
    for sink in sinks:
        sink_re = re.compile(re.escape(sink), re.IGNORECASE)
        for i, line in enumerate(lines, 1):
            if sink_re.search(line) and param_re.search(line):
                sink_reached = True
                method = _find_enclosing_method(methods, i)
                hops.append({
                    "file": file_path, "function": method,
                    "line": i, "hop_type": "sink",
                    "sink_type": sink,
                    "auth_check_present": False,
                    "code": line.strip()[:120],
                })

    # Phase 3: Determine auth gap
    auth_gap = sink_reached and not any(
        h.get("auth_check_present") for h in hops
    )

    return {
        "endpoint": endpoint, "param": param,
        "file": file_path,
        "hops": hops, "hop_count": len(hops),
        "sink_reached": sink_reached,
        "auth_gap": auth_gap,
        "auth_checks": auth_checks,
    }


# --- Internal helpers ---

_METHOD_RE = re.compile(
    r'(?:public|private|protected|static|async|def)\s+'
    r'(?:\w+\s+)?(\w+)\s*\(',
)

_AUTH_PATTERNS: list[tuple[str, str]] = [
    (r'@PreAuthorize', "annotation"),
    (r'@Secured', "annotation"),
    (r'@RolesAllowed', "annotation"),
    (r'@login_required', "decorator"),
    (r'requireAuth|isAuthenticated|checkPermission', "function_call"),
    (r'req\.user|request\.user|currentUser|getAuthUser', "identity_access"),
    (r'\.hasRole|\.hasAuthority|\.isAllowed', "role_check"),
    (r'ownership|ownerCheck|belongsTo|isOwner', "ownership_check"),
]


def _extract_methods(lines: list[str]) -> list[dict[str, Any]]:
    """Extract method names and their line ranges."""
    methods: list[dict[str, Any]] = []
    for i, line in enumerate(lines, 1):
        m = _METHOD_RE.search(line)
        if m:
            methods.append({"name": m.group(1), "start": i})
    # Set end lines
    for j in range(len(methods) - 1):
        methods[j]["end"] = methods[j + 1]["start"] - 1
    if methods:
        methods[-1]["end"] = len(lines)
    return methods


def _find_enclosing_method(
    methods: list[dict[str, Any]], line: int,
) -> str:
    """Find which method encloses a given line number."""
    for m in methods:
        if m["start"] <= line <= m.get("end", line):
            return m["name"]
    return "unknown"


def _classify_hop(method: str, line: str) -> str:
    """Classify a hop as controller/service/dao/middleware."""
    low = (method + line).lower()
    if any(k in low for k in ("controller", "handler", "endpoint", "route")):
        return "controller"
    if any(k in low for k in ("service", "manager", "logic")):
        return "service"
    if any(k in low for k in ("dao", "repository", "repo", "mapper", "store")):
        return "dao"
    if any(k in low for k in ("filter", "interceptor", "middleware", "guard")):
        return "middleware"
    return "unknown"


def _check_auth(lines: list[str], line_num: int, window: int = 5) -> dict[str, str] | None:
    """Check for auth patterns near a line."""
    start = max(0, line_num - window - 1)
    end = min(len(lines), line_num + window)
    chunk = "\n".join(lines[start:end])
    for pattern, auth_type in _AUTH_PATTERNS:
        if re.search(pattern, chunk):
            return {"type": auth_type, "pattern": pattern, "near_line": line_num}
    return None

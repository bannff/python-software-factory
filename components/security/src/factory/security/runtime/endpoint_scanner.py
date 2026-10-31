"""Deterministic endpoint scanner — regex-based discovery.

Scans source code for HTTP endpoint annotations across frameworks.
Returns structured endpoint inventory without LLM inference.
Exposed as security_scan_endpoints MCP tool.
"""
from __future__ import annotations

import re
from typing import Any

# Framework-specific endpoint patterns
FRAMEWORK_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "spring_mvc": [
        (r'@GetMapping\s*\(\s*["\']([^"\']+)', "GET"),
        (r'@PostMapping\s*\(\s*["\']([^"\']+)', "POST"),
        (r'@PutMapping\s*\(\s*["\']([^"\']+)', "PUT"),
        (r'@DeleteMapping\s*\(\s*["\']([^"\']+)', "DELETE"),
        (r'@PatchMapping\s*\(\s*["\']([^"\']+)', "PATCH"),
        (r'@RequestMapping\s*\([^)]*value\s*=\s*["\']([^"\']+)', "ANY"),
        (r'@RequestMapping\s*\(\s*["\']([^"\']+)', "ANY"),
    ],
    "jax_rs": [
        (r'@Path\s*\(\s*["\']([^"\']+)', "ANY"),
        (r'@GET\s', "GET"), (r'@POST\s', "POST"),
        (r'@PUT\s', "PUT"), (r'@DELETE\s', "DELETE"),
    ],
    "flask": [
        (r'@(?:app|blueprint)\.route\s*\(\s*["\']([^"\']+)', "ANY"),
        (r'@(?:app|blueprint)\.(get|post|put|delete)\s*\(\s*["\']([^"\']+)', None),
    ],
    "express": [
        (r'router\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)', None),
        (r'app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)', None),
    ],
    "django": [
        (r'path\s*\(\s*["\']([^"\']+)', "ANY"),
        (r'url\s*\(\s*r?["\']([^"\']+)', "ANY"),
    ],
}


# Parameter extraction patterns
PARAM_PATTERNS: list[tuple[str, str]] = [
    (r'@PathVariable\s+\w+\s+(\w+)', "path"),
    (r'@RequestParam\s+\w+\s+(\w+)', "query"),
    (r'@RequestBody', "body"),
    (r'request\.args\.get\s*\(\s*["\'](\w+)', "query"),
    (r'request\.form\.get\s*\(\s*["\'](\w+)', "form"),
    (r'req\.params\.(\w+)', "path"),
    (r'req\.query\.(\w+)', "query"),
    (r'req\.body\.(\w+)', "body"),
]


def scan_endpoints(
    source_code: str,
    framework: str = "auto",
    file_path: str = "",
) -> list[dict[str, Any]]:
    """Scan source code for HTTP endpoints.

    Args:
        source_code: Raw source code content.
        framework: Framework hint (spring_mvc, flask, etc.) or "auto".
        file_path: File path for context.

    Returns:
        List of endpoint dicts with method, path, file, line, params.
    """
    frameworks = (
        [framework] if framework != "auto"
        else list(FRAMEWORK_PATTERNS.keys())
    )
    endpoints: list[dict[str, Any]] = []
    lines = source_code.splitlines()

    for fw in frameworks:
        patterns = FRAMEWORK_PATTERNS.get(fw, [])
        for pattern, default_method in patterns:
            for i, line in enumerate(lines, 1):
                m = re.search(pattern, line)
                if not m:
                    continue
                groups = m.groups()
                if default_method is None and len(groups) >= 2:
                    method = groups[0].upper()
                    path = groups[1]
                elif groups:
                    method = default_method or "ANY"
                    path = groups[0]
                else:
                    continue
                endpoints.append({
                    "method": method, "path": path,
                    "file": file_path, "line": i,
                    "framework": fw,
                })

    # Extract params for each endpoint
    for ep in endpoints:
        ep["params"] = _extract_params(lines, ep["line"])

    return _deduplicate(endpoints)


def _extract_params(
    lines: list[str], start_line: int, window: int = 15,
) -> list[dict[str, str]]:
    """Extract parameters near an endpoint annotation."""
    params: list[dict[str, str]] = []
    end = min(start_line + window, len(lines))
    chunk = "\n".join(lines[start_line - 1:end])
    for pattern, source in PARAM_PATTERNS:
        for m in re.finditer(pattern, chunk):
            name = m.group(1) if m.lastindex else "body"
            params.append({"name": name, "source": source})
    return params


def _deduplicate(
    endpoints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove duplicate endpoints by (method, path, file)."""
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for ep in endpoints:
        key = (ep["method"], ep["path"], ep["file"])
        if key not in seen:
            seen.add(key)
            result.append(ep)
    return result

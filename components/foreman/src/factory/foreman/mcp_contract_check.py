"""AST inventory and Git-base ratchet for public FastMCP typed boundaries."""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import Any

from .mcp_contract_models import ModelResolver, module_name

_CATEGORY_NAMES = {"deterministic", "operational", "authoring"}
_RAW_EGRESS = {"dict", "list", "tuple", "set", "Any"}
# Registration decorators: ``<mcp|registry|catalog>.tool(...)`` and the
# per-action gate ``gated_tool(...)`` (which calls ``mcp.tool()`` itself, so
# a denied tool never registers — it must stay audited either way).
_TOOL_DECORATOR_ROOTS = {"mcp", "registry", "catalog"}
_TOOL_DECORATOR_NAMES = {"gated_tool"}

def _py_paths(root: Path) -> list[Path]:
    return sorted(root.glob("components/*/src/factory/**/*.py")) + sorted(
        root.glob("bases/*/src/factory/**/*.py")
    )

def _brick(path: str) -> str:
    parts = path.split("/")
    return parts[parts.index("components") + 1] if "components" in parts else parts[parts.index("bases") + 1]

def _sources(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): path.read_text(encoding="utf-8") for path in _py_paths(root)}

def _base_sources(root: Path, base_sha: str) -> dict[str, str]:
    listing = subprocess.run(["git", "ls-tree", "-r", "-z", "--name-only", base_sha, "--", "components", "bases"], cwd=root, capture_output=True)
    if listing.returncode:
        raise ValueError(listing.stderr.decode().strip() or "cannot list base MCP sources")
    paths = [path.decode() for path in listing.stdout.split(b"\0") if b"/src/factory/" in path and path.endswith(b".py")]
    sources: dict[str, str] = {}
    for path in paths:
        shown = subprocess.run(["git", "show", f"{base_sha}:{path}"], cwd=root, capture_output=True)
        if shown.returncode:
            raise ValueError(shown.stderr.decode().strip() or f"cannot read base source: {path}")
        sources[path] = shown.stdout.decode()
    return sources

def _name(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None

def _is_mcp_tool(decorator: ast.expr) -> bool:
    call = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(call, ast.Name):
        return call.id in _TOOL_DECORATOR_NAMES
    return (
        isinstance(call, ast.Attribute)
        and call.attr == "tool"
        and isinstance(call.value, ast.Name)
        and call.value.id in _TOOL_DECORATOR_ROOTS
    )

def _category(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.Call | None:
    return next((
        item for item in node.decorator_list
        if isinstance(item, ast.Call)
        and (_name(item.func) in _CATEGORY_NAMES
             or (_name(item.func) or "").removesuffix("_decorator") in _CATEGORY_NAMES
             or _name(item.func) == "typed")
    ), None)

def _raw_egress(annotation: ast.expr | None) -> bool:
    return _name(annotation.value) in _RAW_EGRESS if isinstance(annotation, ast.Subscript) else _name(annotation) in _RAW_EGRESS

_NATIVE_TRANSPORT_PATH = "bases/mcp_server/src/factory/mcp_server/runtime/progressive_invocation.py"

def _imports_native_transport_marker(tree: ast.Module) -> bool:
    """Require the canonical marker import, not a same-named local decorator."""
    return any(
        isinstance(item, ast.ImportFrom)
        and item.module in {"mcp_contracts", ".mcp_contracts"}
        and any(alias.name == "native_transport_egress" for alias in item.names)
        for item in tree.body
    )

def _native_transport_output(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    path: str,
    marker_imported: bool,
) -> ast.expr | None:
    """Return the DTO for the sole allowed native-transport endpoint."""
    if path != _NATIVE_TRANSPORT_PATH or node.name != "call_brick_tool" or not marker_imported:
        return None
    for item in node.decorator_list:
        if not isinstance(item, ast.Call) or _name(item.func) != "native_transport_egress":
            continue
        output = next((keyword.value for keyword in item.keywords
                       if keyword.arg == "output_model"), None)
        return output if _name(output) == "NativeTransportOutput" else None
    return None

def _tool_result_issue(resolver: ModelResolver, module: str, annotation: ast.expr | None,
                       brick: str, output_reference: str | None) -> str | None:
    if not isinstance(annotation, ast.Subscript) or _name(annotation.value) != "ToolResult":
        return "output_not_tool_result"
    if isinstance(annotation.slice, ast.Tuple):
        return "tool_result_nonconcrete_output"
    status = resolver.inspect(module, annotation.slice, brick)
    if status.state != "valid":
        return "tool_result_nonconcrete_output"
    return None if status.reference == output_reference else "tool_result_output_model_mismatch"

def _identity(item: dict[str, str]) -> tuple[str, str, str]:
    return item["brick"], item["path"], item["tool"]

def inventory_mcp_contracts(workspace_root: Path | None = None, *, sources: dict[str, str] | None = None) -> list[dict[str, str]]:
    """List typed-boundary violations for public FastMCP functions."""
    root = workspace_root or Path.cwd()
    source_map = sources if sources is not None else _sources(root)
    resolver = ModelResolver(source_map)
    violations: list[dict[str, str]] = []
    for path, source in source_map.items():
        module = module_name(path)
        if module is None:
            continue
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            continue
        brick = _brick(path)
        marker_imported = _imports_native_transport_marker(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not any(
                _is_mcp_tool(item) for item in node.decorator_list
            ):
                continue
            category = _category(node)
            native_output = _native_transport_output(node, path, marker_imported)
            keywords = {item.arg: item.value for item in category.keywords} if category else {}
            if native_output is not None:
                keywords["output_model"] = native_output
            issues: list[str] = []
            statuses = {
                kind: resolver.inspect(module, keywords.get(f"{kind}_model"), brick)
                if category else None
                for kind in ("input", "output")
            }
            for kind, status in statuses.items():
                if status is None:
                    issues.append(f"missing_{kind}_model")
                elif status.state != "valid":
                    issues.append(f"{status.state}_{kind}_model")
                elif not status.extra_forbid:
                    issues.append(f"{kind}_model_extra_not_forbid")
            output = statuses["output"]
            if output is not None and output.state == "valid" and native_output is None:
                issue = _tool_result_issue(resolver, module, node.returns, brick, output.reference)
                if issue:
                    issues.append(issue)
            if native_output is None and _raw_egress(node.returns):
                issues.append("raw_container_egress")
            for issue in issues:
                violations.append({"brick": brick, "path": path, "tool": node.name, "issue": issue})
    return violations

def check_mcp_contracts(workspace_root: Path | None = None, base_sha: str | None = None) -> dict[str, Any]:
    """Block newly introduced untyped tool identities while retaining legacy debt."""
    root = workspace_root or Path.cwd()
    current = inventory_mcp_contracts(root)
    if not base_sha:
        return {"check": "mcp_contracts", "passed": True, "mode": "informational", "message": "base_sha absent; MCP contract ratchet not enforced", "violations": current, "new_violations": [], "legacy_violations": current, "resolved_violations": []}
    verify = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{base_sha}^{{commit}}"], cwd=root, capture_output=True)
    if verify.returncode:
        return {"check": "mcp_contracts", "passed": False, "mode": "ratchet", "error": "base_sha does not resolve", "violations": current}
    try:
        baseline = inventory_mcp_contracts(root, sources=_base_sources(root, base_sha))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return {"check": "mcp_contracts", "passed": False, "mode": "ratchet", "error": str(exc), "violations": current}
    old_ids, current_ids = {_identity(item) for item in baseline}, {_identity(item) for item in current}
    new = [item for item in current if _identity(item) not in old_ids]
    legacy = [item for item in current if _identity(item) in old_ids]
    resolved = [item for item in baseline if _identity(item) not in current_ids]
    return {"check": "mcp_contracts", "passed": not new, "mode": "ratchet", "violations": current, "new_violations": new, "legacy_violations": legacy, "resolved_violations": resolved}

__all__ = ["check_mcp_contracts", "inventory_mcp_contracts"]

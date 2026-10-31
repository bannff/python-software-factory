"""Sync deep-scanned pip dependencies into BRICK.yaml files.

Runs the deep AST scanner across all (or specified) bricks and writes
a ``pip_packages`` list into each BRICK.yaml.  This is the single
source of truth — the scanner produces the data, BRICK.yaml caches it,
and ``resolve_dependencies`` reads the cache for fast project creation.
"""

from pathlib import Path
from typing import Any

import yaml

from .deps_map import IMPORT_TO_PACKAGE, STDLIB as _STDLIB
from .deps import (
    _find_brick_src,
    _find_brick_yaml,
    _scan_brick_imports,
)


def _all_brick_names(workspace_root: Path) -> list[str]:
    """Discover all brick names in the workspace."""
    names: list[str] = []
    for prefix in ["components", "bases"]:
        parent = workspace_root / prefix
        if not parent.exists():
            continue
        for d in sorted(parent.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                src = d / "src" / "factory" / d.name
                if src.exists():
                    names.append(d.name)
    return names


def _compute_pip_packages(brick_name: str, workspace_root: Path) -> list[str]:
    """Deep-scan a brick and return sorted pip package specs."""
    src = _find_brick_src(brick_name, workspace_root)
    if src is None:
        return []
    _, third_party = _scan_brick_imports(src)
    return sorted(
        {IMPORT_TO_PACKAGE[imp] for imp in third_party if imp in IMPORT_TO_PACKAGE}
    )


def _update_brick_yaml(brick_yaml: Path, packages: list[str]) -> bool:
    """Update pip_packages in a BRICK.yaml, preserving other fields.

    Returns True if the file was changed.
    """
    try:
        raw = brick_yaml.read_text()
        data = yaml.safe_load(raw) or {}
    except (OSError, yaml.YAMLError):
        return False

    old = data.get("pip_packages")
    if old == packages:
        return False

    data["pip_packages"] = packages
    brick_yaml.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return True


def sync_brick_deps(
    bricks: list[str] | None = None,
    workspace_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Deep-scan bricks and write pip_packages into their BRICK.yaml.

    Args:
        bricks: Brick names to sync. None means all bricks.
        workspace_root: Workspace root. Defaults to cwd.
        dry_run: If True, compute but don't write.

    Returns:
        Summary with per-brick results and unmapped imports.
    """
    if workspace_root is None:
        workspace_root = Path.cwd()

    targets = bricks if bricks else _all_brick_names(workspace_root)
    results: list[dict[str, Any]] = []
    total_updated = 0
    total_unchanged = 0
    all_unmapped: set[str] = set()

    for name in sorted(targets):
        src = _find_brick_src(name, workspace_root)
        if src is None:
            results.append({"brick": name, "status": "not_found"})
            continue

        brick_yaml = _find_brick_yaml(name, workspace_root)
        if brick_yaml is None:
            results.append({"brick": name, "status": "no_brick_yaml"})
            continue

        # Deep scan
        _, third_party = _scan_brick_imports(src)
        packages = sorted(
            {IMPORT_TO_PACKAGE[imp] for imp in third_party if imp in IMPORT_TO_PACKAGE}
        )
        unmapped = {imp for imp in third_party if imp not in IMPORT_TO_PACKAGE}
        all_unmapped.update(unmapped)

        if dry_run:
            old = yaml.safe_load(brick_yaml.read_text()).get("pip_packages")
            changed = old != packages
            results.append({
                "brick": name,
                "status": "would_update" if changed else "unchanged",
                "pip_packages": packages,
                "unmapped_imports": sorted(unmapped) if unmapped else [],
            })
            if changed:
                total_updated += 1
            else:
                total_unchanged += 1
        else:
            changed = _update_brick_yaml(brick_yaml, packages)
            results.append({
                "brick": name,
                "status": "updated" if changed else "unchanged",
                "pip_packages": packages,
                "unmapped_imports": sorted(unmapped) if unmapped else [],
            })
            if changed:
                total_updated += 1
            else:
                total_unchanged += 1

    return {
        "status": "success",
        "dry_run": dry_run,
        "total_bricks": len(targets),
        "updated": total_updated,
        "unchanged": total_unchanged,
        "unmapped_imports": sorted(all_unmapped),
        "bricks": results,
    }

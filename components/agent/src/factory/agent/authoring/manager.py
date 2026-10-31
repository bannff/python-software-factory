"""CRUD operations manager for authoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml

from .paths import AuthoringPaths
from .roots import ROOT_SPECS, AuthoringRootUnavailable
from .validation import (
    AuthoringError,
    assert_within_root,
    ensure_id,
    ensure_tool_module,
    validate_config,
    validate_tool_module,
    ConfigKind,
)


class AuthoringManager:
    """CRUD operations scoped to a config directory."""

    def __init__(self, config_root: Path):
        self.paths = AuthoringPaths(root=config_root)

    def _prepare_dir(self, path: Path) -> None:
        """Create a write directory, typing an unusable config root as such.

        The mkdir is where a broken ``FACTORY_AGENT_CONFIG_DIR`` surfaces, so it
        is the one OSError that is a ROOT problem rather than a write problem.
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            variable, _default = ROOT_SPECS["config"]
            raise AuthoringRootUnavailable(variable, self.paths.root, error) from error

    def list_items(self, kind: ConfigKind) -> list[dict[str, Any]]:
        """List items of a given kind."""
        if kind == "settings":
            return [{"kind": "settings", "path": str(self.paths.settings_file),
                     "exists": self.paths.settings_file.exists()}]

        base = self._get_base_dir(kind)
        if not base.exists():
            return []

        pattern = "*.py" if kind == "tool" else "*.yaml"
        items: list[dict[str, Any]] = []
        for file_path in sorted(base.glob(pattern)):
            if kind == "tool" and file_path.name.startswith("_"):
                continue
            items.append({"kind": kind, "id": file_path.stem, "path": str(file_path)})
        return items

    def read_yaml_config(self, kind: Literal["agent", "swarm", "graph", "squad"], item_id: str) -> dict[str, Any]:
        """Read a YAML config file."""
        item_id = ensure_id(item_id)
        base = self._get_base_dir(kind)
        path = base / f"{item_id}.yaml"
        assert_within_root(self.paths.root, path)
        if not path.exists():
            raise AuthoringError(f"Not found: {kind} '{item_id}'")
        content = yaml.safe_load(path.read_text())
        if not isinstance(content, dict):
            raise AuthoringError("Config file must parse to a mapping")
        return content

    def write_yaml_config(self, kind: Literal["agent", "swarm", "graph", "squad"], config: dict[str, Any]) -> dict[str, Any]:
        """Write a YAML config file."""
        config_id = ensure_id(str(config.get("id", "")))
        validation = validate_config(kind, config)
        if not validation.get("ok"):
            raise AuthoringError(f"Invalid {kind} config: {validation.get('error')}")

        base = self._get_base_dir(kind)
        self._prepare_dir(base)
        path = base / f"{config_id}.yaml"
        assert_within_root(self.paths.root, path)
        path.write_text(yaml.safe_dump(config, sort_keys=False))
        return {"ok": True, "id": config_id, "path": str(path)}

    def read_fork_provenance(self, kind: Literal["agent", "swarm", "graph", "squad"], item_id: str) -> str | None:
        """Return the built-in id a user item was forked from, or ``None``.

        Provenance lives in a sidecar ``<id>.fork.json`` rather than inside
        the config itself, since ``AgentConfig``/etc. use ``extra="forbid"``
        and adding a field there would be a schema change with a much
        wider blast radius than this row (33, feature-map) needs.
        """
        item_id = ensure_id(item_id)
        path = self._get_base_dir(kind) / f"{item_id}.fork.json"
        assert_within_root(self.paths.root, path)
        if not path.exists():
            return None
        import json
        data = json.loads(path.read_text())
        source = data.get("source_id")
        return source if isinstance(source, str) else None

    def write_fork_provenance(
        self, kind: Literal["agent", "swarm", "graph", "squad"], item_id: str, source_id: str,
    ) -> None:
        """Record that ``item_id`` was forked from built-in ``source_id``."""
        import json
        item_id, source_id = ensure_id(item_id), ensure_id(source_id)
        path = self._get_base_dir(kind) / f"{item_id}.fork.json"
        assert_within_root(self.paths.root, path)
        path.write_text(json.dumps({"source_id": source_id}))

    def delete_fork_provenance(self, kind: Literal["agent", "swarm", "graph", "squad"], item_id: str) -> None:
        """Remove the fork-provenance sidecar, if any (best-effort)."""
        item_id = ensure_id(item_id)
        path = self._get_base_dir(kind) / f"{item_id}.fork.json"
        assert_within_root(self.paths.root, path)
        path.unlink(missing_ok=True)

    def delete_yaml_config(self, kind: Literal["agent", "swarm", "graph", "squad"], item_id: str) -> dict[str, Any]:
        """Delete a YAML config file (and any fork-provenance sidecar)."""
        item_id = ensure_id(item_id)
        base = self._get_base_dir(kind)
        path = base / f"{item_id}.yaml"
        assert_within_root(self.paths.root, path)
        if not path.exists():
            return {"ok": False, "error": "not_found", "id": item_id}
        path.unlink()
        self.delete_fork_provenance(kind, item_id)
        return {"ok": True, "id": item_id}

    def read_settings(self) -> dict[str, Any]:
        """Read settings.yaml."""
        path = self.paths.settings_file
        assert_within_root(self.paths.root, path)
        if not path.exists():
            return {}
        content = yaml.safe_load(path.read_text())
        return content if isinstance(content, dict) else {}

    def write_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Write settings.yaml."""
        if not isinstance(settings, dict):
            raise AuthoringError("settings must be a mapping")
        path = self.paths.settings_file
        assert_within_root(self.paths.root, path)
        self._prepare_dir(path.parent)
        path.write_text(yaml.safe_dump(settings, sort_keys=False))
        return {"ok": True, "path": str(path)}

    def read_tool_module(self, module_name: str) -> dict[str, Any]:
        """Read a tool module."""
        module_name = ensure_tool_module(module_name)
        path = self.paths.tools_dir / f"{module_name}.py"
        assert_within_root(self.paths.root, path)
        if not path.exists():
            raise AuthoringError(f"Not found: tool module '{module_name}'")
        return {"ok": True, "module": module_name, "code": path.read_text()}

    def write_tool_module(self, module_name: str, code: str) -> dict[str, Any]:
        """Write a tool module."""
        module_name = ensure_tool_module(module_name)
        validation = validate_tool_module(code)
        if not validation.get("ok"):
            raise AuthoringError(f"Invalid Python code: {validation.get('error')}")
        path = self.paths.tools_dir / f"{module_name}.py"
        assert_within_root(self.paths.root, path)
        self._prepare_dir(path.parent)
        path.write_text(code)
        return {"ok": True, "module": module_name, "path": str(path)}

    def delete_tool_module(self, module_name: str) -> dict[str, Any]:
        """Delete a tool module."""
        module_name = ensure_tool_module(module_name)
        path = self.paths.tools_dir / f"{module_name}.py"
        assert_within_root(self.paths.root, path)
        if not path.exists():
            return {"ok": False, "error": "not_found", "module": module_name}
        path.unlink()
        return {"ok": True, "module": module_name}

    def _get_base_dir(self, kind: ConfigKind) -> Path:
        """Get base directory for a config kind."""
        dirs = {
            "agent": self.paths.agents_dir,
            "swarm": self.paths.swarms_dir,
            "graph": self.paths.graphs_dir,
            "squad": self.paths.squads_dir,
            "tool": self.paths.tools_dir,
        }
        if kind not in dirs:
            raise AuthoringError(f"Unknown kind: {kind}")
        return dirs[kind]

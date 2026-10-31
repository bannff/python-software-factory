from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from factory.permissions.runtime.models import PolicyDefinition
from factory.permissions.runtime.ports import PolicyStore


@dataclass
class FilesystemPolicyStore(PolicyStore):
    config_dir: Path
    policies_subdir: str = "policies"

    _last_error: str | None = None

    def _policies_dir(self) -> Path:
        return (self.config_dir / self.policies_subdir).resolve()

    def load_policies(self) -> list[PolicyDefinition]:
        policies_dir = self._policies_dir()
        if not policies_dir.exists():
            self._last_error = None
            return []

        policies: list[PolicyDefinition] = []
        try:
            for path in sorted(policies_dir.glob("*.yaml")):
                raw = yaml.safe_load(path.read_text())
                if not isinstance(raw, dict):
                    raise ValueError(f"Policy file must parse to a mapping: {path}")
                policies.append(PolicyDefinition.model_validate(raw))
            self._last_error = None
            return policies
        except Exception as e:
            self._last_error = f"{type(e).__name__}: {e}"
            return []

    def health_check(self) -> dict[str, object]:
        policies_dir = self._policies_dir()
        exists = policies_dir.exists()
        ok = exists
        if self._last_error:
            ok = False
        return {
            "ok": ok,
            "policies_dir": str(policies_dir),
            "exists": exists,
            "last_error": self._last_error,
        }

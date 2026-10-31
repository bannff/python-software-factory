"""Bounded temporary materialization of frozen skill bytes."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from .canonical import canonical_bytes, sha256
from .descriptors import SkillBundle


class SkillMaterializer:
    def __init__(self) -> None:
        self._temporary = TemporaryDirectory(prefix="agent-manifest-skills-")
        self.root = Path(self._temporary.name).resolve()
        self._cache: dict[str, Path] = {}

    def materialize(self, bundle: SkillBundle) -> Path | None:
        if not bundle.names:
            return None
        if bundle.digest != sha256(canonical_bytes([
            item.model_dump(mode="json") for item in bundle.files
        ])):
            raise ValueError("skill bundle digest mismatch")
        if bundle.digest.value in self._cache:
            return self._cache[bundle.digest.value]
        root = self.root / bundle.digest.value
        for item in bundle.files:
            path = root / item.path
            if root not in path.resolve().parents:
                raise ValueError("skill file escapes bundle root")
            if item.digest != sha256(item.content.encode("utf-8")):
                raise ValueError("skill file digest mismatch")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item.content, encoding="utf-8")
        self._cache[bundle.digest.value] = root
        return root

    def close(self) -> None:
        self._temporary.cleanup()


__all__ = ["SkillMaterializer"]

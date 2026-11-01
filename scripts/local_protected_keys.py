"""Mint-once local protected-content keys for the Companion-X launcher.

Stores encrypted at rest (owner secrets, credential slots, protected artifacts)
fail closed without these keys. Unlike the per-run MCP token they must outlive
the process: rotating them would orphan every stored secret. Emits ``export``
lines for the launcher to eval; emits nothing when the operator already set a key.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

KEK = "FACTORY_PROTECTED_CONTENT_LOCAL_KEK"
INDEX = "FACTORY_PROTECTED_CONTENT_LOCAL_INDEX_KEY"


def _mint() -> dict[str, str]:
    return {name: base64.b64encode(os.urandom(32)).decode() for name in (KEK, INDEX)}


def _load_or_create(path: Path) -> dict[str, str]:
    if path.exists():
        return json.loads(path.read_text())
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    keys = _mint()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(keys, handle)
    return keys


def exports(path: Path, environ: dict[str, str]) -> list[str]:
    if environ.get(KEK):
        return []
    keys = _load_or_create(path)
    return [f"export {name}={keys[name]}" for name in (KEK, INDEX)]


if __name__ == "__main__":
    print("\n".join(exports(Path(sys.argv[1]), dict(os.environ))))
